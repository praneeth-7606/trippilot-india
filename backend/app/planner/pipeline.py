"""LangGraph workflow: research → route stops → deterministic schedule/validate.

No model is allowed to invent routes or override hard constraints. Phase 1 uses
structured input; a natural-language provider can be selected independently.
"""
import re
from datetime import datetime, timedelta, timezone, time
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app.config import get_settings
from app.models.itinerary import (ItineraryVersion, PlanStatus, PlaceCategory,
    TravelMode, FeasibilityIssue)
from app.models.trip import TripRequest
from app.planner import feasibility
from app.planner.scheduler import build_days, build_budget
from app.planner.stops import plan_stops
from app.planner.timeutil import at
from app.services.directions import build_route_option, parse_leg
from app.services.maps import MapsService
from app.services.search import SearchService
from app.services.serpapi import SerpApiService
from app.services.weather import WeatherService


class State(TypedDict, total=False):
    request: TripRequest
    version: int
    data: dict
    result: ItineraryVersion


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class PlanningPipeline:
    def __init__(self, budget=None):
        self.settings = get_settings()
        self.provider = SerpApiService(budget)
        self.budget = self.provider.budget
        self.maps, self.search = MapsService(self.provider), SearchService(self.provider)
        graph = StateGraph(State)
        graph.add_node("research", self.research)
        graph.add_node("route_stops", self.route_stops)
        graph.add_node("schedule_validate", self.schedule_validate)
        graph.add_edge(START, "research")
        graph.add_conditional_edges("research", lambda s: "failed" if "result" in s else "continue",
                                    {"failed": END, "continue": "route_stops"})
        graph.add_edge("route_stops", "schedule_validate")
        graph.add_edge("schedule_validate", END)
        self.graph = graph.compile()

    def plan(self, req, version=1):
        return self.graph.invoke({"request": req, "version": version})["result"]

    def route(self, origin, destination, mode, name, avoid_tolls=False):
        params = {"start_addr": origin, "end_addr": destination,
            "travel_mode": "9" if mode == TravelMode.two_wheeler else "0",
            "distance_unit": "0", "gl": "in", "hl": "en"}
        if avoid_tolls:
            params["avoid"] = "tolls"
        response = self.provider.search("google_maps_directions", params,
            f"dir:{slug(origin)}:{slug(destination)}:{mode.value}")
        options = [build_route_option([parse_leg(response, f"{name}-{i}", origin, destination, mode, i)],
            f"{name}-{i}", "Recommended route" if i == 0 else "Alternative route")
            for i in range(len(response.data.get("directions", [])))]
        if not options:
            raise ValueError("Provider returned no usable route")
        return options[0], options[1:]

    def research(self, state):
        req = state["request"]
        dest = req.destinations[0]
        mode = TravelMode.two_wheeler if req.transport_mode == "motorcycle" else TravelMode.driving
        try:
            outbound, alternatives = self.route(req.origin, dest, mode, "out", req.road.avoid_tolls)
            inbound, _ = (self.route(dest, req.origin, mode, "back", req.road.avoid_tolls)
                          if req.includes_return else (outbound, []))
        except Exception as exc:
            return {"result": ItineraryVersion(version=state["version"], created_at=datetime.now(timezone.utc),
                status="failed", days=[], issues=[FeasibilityIssue(code="provider_unavailable", severity="error",
                message=str(exc))], notes=["Required route data unavailable. Check credentials or use the Munnar fixture scenario."])}
        data = {"out": outbound, "back": inbound, "alternatives": alternatives, "notes": [], "incomplete": False}
        queries = {
            "attractions": (f"{dest} tourist attractions", PlaceCategory.attraction, f"places:{slug(dest)}:attractions", 60),
            "food": (f"vegetarian restaurants on {req.origin} to {dest} route", PlaceCategory.restaurant, "places:route:food", 40),
            "fuel": (f"petrol stations {req.origin} to {dest}", PlaceCategory.fuel, "places:route:fuel", 12),
            "washroom": (f"public washrooms {req.origin} to {dest}", PlaceCategory.washroom, "places:route:washroom", 10),
            "rest": (f"rest areas {req.origin} to {dest}", PlaceCategory.rest, "places:route:rest", 15),
            "destination_food": (f"{'vegetarian ' if req.food.vegetarian else ''}restaurants {dest}", PlaceCategory.restaurant, f"places:{slug(dest)}:food", 40),
        }
        for name, (query, category, key, visit) in queries.items():
            try:
                data[name] = self.maps.find_places(query, category, key, visit_minutes=visit)
            except Exception:
                data[name] = []
                data["notes"].append(f"{name.replace('_', ' ')} provider unavailable; this part of the plan needs confirmation.")
                data["incomplete"] = True
        data["weather"], data["advisories"] = [], []
        anchor = outbound.legs[-1].to_point
        end = req.return_date or req.start_date
        if anchor:
            dates = [req.start_date + timedelta(days=i) for i in range((end-req.start_date).days+1)]
            data["weather"] = WeatherService().forecast(anchor.lat, anchor.lng, dates, f"weather:{slug(dest)}")
        try:
            data["advisories"] = self.search.advisories(f"site:keralatourism.org {dest} visitor information", f"search:{slug(dest)}:advisory")
        except Exception:
            data["notes"].append("Official information lookup unavailable; check attraction rules separately.")
        return {"data": data}

    def route_stops(self, state):
        data, req = state["data"], state["request"]
        for key, departure in [("out", at(req.start_date, req.departure_time)),
                                ("back", at(req.return_date or req.start_date, time(15)))]:
            data[key+"_stops"] = plan_stops(data[key], departure, req.food, req.road, req.vehicles,
                data["food"], data["fuel"], data["washroom"], data["rest"])
        return {"data": data}

    def schedule_validate(self, state):
        req, data = state["request"], state["data"]
        notes = list(data["notes"])
        if self.settings.fixture_mode:
            notes.append("SYNTHETIC FIXTURE mode: routes, places, hours and weather are illustrative test data, not live search results.")
        notes += ["Budget subtotal excludes accommodation, tickets, tolls and local travel; it is not a complete trip price.",
                  "Stop detours and destination hops are geometry-based estimates, not routed travel-time measurements.",
                  "Fuel suggestions assume a full tank at the start of each leg. Current fuel, availability and multi-leg range need confirmation."]
        for attempt in range(4):
            days, excluded, _ = build_days(req, data["out"], data["back"], data["out_stops"], data["back_stops"],
                data["attractions"], data["destination_food"], drop_count=attempt)
            result = ItineraryVersion(version=state["version"], created_at=datetime.now(timezone.utc), status="ready",
                days=days, excluded=excluded, route=data["out"], route_alternatives=data["alternatives"],
                weather=data["weather"], advisories=data["advisories"], notes=notes,
                budget=build_budget(req, data["out"], data["back"]))
            result.issues = feasibility.check(req, result)
            if not any(i.severity == "error" for i in result.issues):
                break
        if any(i.severity == "error" for i in result.issues) or data["incomplete"]:
            result.status = PlanStatus.partial
        return {"result": result}
