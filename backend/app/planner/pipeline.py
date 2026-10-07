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
    TravelMode, FeasibilityIssue, Advisory)
from app.models.trip import TripRequest
from app.planner import feasibility
from app.planner.scheduler import build_days, build_route_days, build_budget
from app.planner.stops import plan_stops, route_midpoint
from app.planner.timeutil import at
from app.services.directions import build_route_option, parse_leg
from app.services.maps import MapsService
from app.services.search import SearchService
from app.services.serpapi import SerpApiService
from app.services.weather import WeatherService


class State(TypedDict, total=False):
    request: TripRequest
    version: int
    route_option: int
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

    def plan(self, req, version=1, route_option=0):
        return self.graph.invoke({"request": req, "version": version, "route_option": route_option})["result"]

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
        cities = req.destinations
        mode = TravelMode.two_wheeler if req.transport_mode == "motorcycle" else TravelMode.driving
        points = [req.origin] + cities
        try:
            legs = []
            for i in range(len(points) - 1):
                leg, leg_alts = self.route(points[i], points[i + 1], mode, f"leg{i}", req.road.avoid_tolls)
                legs.append({"city": points[i + 1], "route": leg, "alternatives": leg_alts})
            chosen = max(0, min(state.get("route_option", 0), len(legs[0]["alternatives"])))
            if chosen:
                legs[0]["route"] = legs[0]["alternatives"][chosen - 1]
            inbound, _ = (self.route(cities[-1], req.origin, mode, "back", req.road.avoid_tolls)
                          if req.includes_return else (legs[0]["route"], []))
        except Exception as exc:
            return {"result": ItineraryVersion(version=state["version"], created_at=datetime.now(timezone.utc),
                status="failed", days=[], issues=[FeasibilityIssue(code="provider_unavailable", severity="error",
                message=str(exc))], notes=["Required route data unavailable. Check credentials or use the Munnar fixture scenario."])}
        first = legs[0]["route"]
        combined = build_route_option([leg for seg in legs for leg in seg["route"].legs],
                                      "journey", "Multi-city route" if len(legs) > 1 else first.label)
        data = {"legs": legs, "out": combined, "back": inbound,
                "alternatives": legs[0]["alternatives"], "route_option": chosen,
                "notes": [], "incomplete": False}
        stop_anchor = route_midpoint(first)
        road_queries = {
            "food": ("vegetarian restaurants" if req.food.vegetarian else "restaurants", PlaceCategory.restaurant, "places:route:food", 40),
            "fuel": ("petrol pumps", PlaceCategory.fuel, "places:route:fuel", 12),
            "washroom": ("public toilets", PlaceCategory.washroom, "places:route:washroom", 10),
            "rest": ("cafes", PlaceCategory.rest, "places:route:rest", 15),
        }
        for name, (query, category, key, visit) in road_queries.items():
            try:
                data[name] = self.maps.find_places(query, category, key, visit_minutes=visit, near=stop_anchor)
            except Exception:
                data[name] = []
                data["notes"].append(f"{name} provider unavailable; this part of the plan needs confirmation.")
                data["incomplete"] = True
        for seg in legs:
            city = seg["city"]
            anchor = seg["route"].legs[-1].to_point
            for name, (query, category, key, visit) in {
                "attractions": (f"{city} tourist attractions", PlaceCategory.attraction, f"places:{slug(city)}:attractions", 60),
                "food": (f"{'vegetarian ' if req.food.vegetarian else ''}restaurants {city}", PlaceCategory.restaurant, f"places:{slug(city)}:food", 40),
            }.items():
                try:
                    seg[name] = self.maps.find_places(query, category, key, visit_minutes=visit, near=anchor)
                except Exception:
                    seg[name] = []
                    data["notes"].append(f"{city} {name} unavailable; this part of the plan needs confirmation.")
                    data["incomplete"] = True
        data["weather"], data["advisories"] = [], []
        end = req.return_date or req.start_date
        dates = [req.start_date + timedelta(days=i) for i in range((end - req.start_date).days + 1)]
        for seg in legs:
            anchor = seg["route"].legs[-1].to_point
            if anchor:
                data["weather"] += WeatherService().forecast(anchor.lat, anchor.lng, dates, f"weather:{slug(seg['city'])}")
        try:
            data["advisories"] = self.search.advisories(
                f"tourist visitor information {' '.join(cities)}", f"search:{slug(cities[-1])}:advisory")
        except Exception:
            data["notes"].append("Official information lookup unavailable; check attraction rules separately.")
        for seg in legs:
            city = seg["city"]
            data["advisories"].append(Advisory(
                text=(f"Hotels in {city}: compare options for your dates and party size; "
                      "room costs below use your estimate and no reservation is made."),
                url=(f"https://www.google.com/travel/hotels?q=hotels+{city.replace(' ', '+')}"
                     f"&g2lb=2502548%2C4208997%2C4270441%2C4306835%2C4317915%2C4328159%2C4356900%2C4374861%2C4401769%2C4419364%2C4425457%2C4515404%2C4545892%2C4567520%2C4596364%2C4605861%2C4754603%2C4758499%2C4770265%2C4786958%2C4797133%2C4814050%2C4827382%2C4834155%2C4844059%2C4859907%2C4864715%2C4874190%2C4886089%2C4895829%2C4902277%2C4908684%2C4913948%2C4914646%2C4916193%2C4920132%2C4926166%2C4927596%2C4936396%2C4949696%2C4949789%2C4950826%2C5033506%2C5037392%2C5038748%2C5042727%2C5059868%2C5079782%2C5114394%2C5128638&hl=en&gl=in"),
                retrieved_at=datetime.now(timezone.utc),
            ))
        return {"data": data}

    def route_stops(self, state):
        data, req = state["data"], state["request"]
        for i, seg in enumerate(data["legs"]):
            departure = at(req.start_date, req.departure_time) if i == 0 else at(req.start_date, time(8, 30))
            seg["stops"] = plan_stops(seg["route"], departure, req.food, req.road, req.vehicles,
                data["food"], data["fuel"], data["washroom"], data["rest"])
            if not self.settings.fixture_mode and seg["stops"]:
                self.verify_stop_legs(data, f"leg{i}", req, seg)
        if req.includes_return:
            data["back_stops"] = plan_stops(data["back"], at(req.return_date or req.start_date, time(15)),
                req.food, req.road, req.vehicles, data["food"], data["fuel"], data["washroom"], data["rest"])
            if not self.settings.fixture_mode and data["back_stops"]:
                self.verify_stop_legs(data, "back", req)
        else:
            data["back_stops"] = []
        # Refresh the combined journey route after stop-leg verification.
        first_label = data["legs"][0]["route"].label
        data["out"] = build_route_option([leg for seg in data["legs"] for leg in seg["route"].legs],
                                         "journey", "Multi-city route" if len(data["legs"]) > 1 else first_label)
        # Single-city compatibility for the legacy schedule path.
        data["out_stops"] = data["legs"][0]["stops"]
        data["attractions"] = data["legs"][0].get("attractions", [])
        data["destination_food"] = data["legs"][0].get("food", [])
        return {"data": data}

    def verify_stop_legs(self, data, key, req, seg=None):
        """Route the actual selected stop chain before accepting its schedule.

        Calls are bounded by the existing per-plan search budget. If a leg is
        unavailable the original estimates remain explicitly partial.
        """
        base = seg["route"] if seg is not None else data[key]
        stops = seg["stops"] if seg is not None else data[key+"_stops"]
        previous, display_name = base.legs[0].from_name, base.legs[0].from_name
        legs, updates = [], []
        elapsed = 0
        try:
            for i, stop in enumerate(stops):
                point = stop.place.location
                target = f"{point.lat},{point.lng}" if point else stop.place.address or stop.place.name
                option, _ = self.route(previous, target, base.legs[0].travel_mode, f"{key}-stop-{i}", req.road.avoid_tolls)
                leg = option.legs[0]
                leg.from_name, leg.to_name = display_name, stop.place.name
                legs.append(leg)
                elapsed += leg.duration_min
                updates.append((stop, elapsed, leg.duration_min))
                previous, display_name = target, stop.place.name
            final, _ = self.route(previous, base.legs[-1].to_name, base.legs[0].travel_mode,
                                   f"{key}-arrival", req.road.avoid_tolls)
            final.legs[0].from_name = display_name
            legs.extend(final.legs)
            routed = build_route_option(legs, base.id, "Route with verified stop legs")
            extra = routed.total_duration_min - base.total_duration_min
            for stop, progress, approach in updates:
                stop.progress_minutes, stop.detour_minutes = progress, 0
                stop.reason = (f"Routed drive from the previous stop: {approach} min. "
                    f"The complete stop chain changes driving time by {extra:+d} min vs the direct route. "
                    "Confirm opening hours, dietary needs and facilities with the venue.")
            if seg is not None:
                seg["route"] = routed
            else:
                data[key] = routed
            data["notes"].append(f"{key.capitalize()}bound stop chain verified with Directions: "
                f"{routed.total_distance_km} km, {routed.total_duration_min} driving minutes, "
                f"{extra:+d} min vs the direct route, excluding dwell time.")
        except Exception:
            data["incomplete"] = True
            data["notes"].append(f"{key.capitalize()}bound stop-leg routing unavailable; remaining detours are estimates.")

    def schedule_validate(self, state):
        req, data = state["request"], state["data"]
        multi = len(req.destinations) > 1
        notes = list(data["notes"])
        if self.settings.fixture_mode:
            notes.append("SYNTHETIC FIXTURE mode: routes, places, hours and weather are illustrative test data, not live search results.")
        if multi:
            notes.append(f"Multi-city route: {' → '.join([req.origin] + req.destinations)}"
                         + (" → " + req.origin if req.includes_return else "") + ".")
        notes += ["Budget figures use your estimates and assumed fuel/food rates; hotel links open live search results and no reservation is made.",
                  "Destination hops remain geometry-based estimates. Road-stop legs use Directions when available; fixtures and failed stop-leg lookups remain estimates.",
                  "Fuel suggestions assume a full tank at the start of each leg. Current fuel, availability and multi-leg range need confirmation."]
        journey_km = (sum(seg["route"].total_distance_km for seg in data["legs"])
                      + (data["back"].total_distance_km if req.includes_return else 0))
        for attempt in range(4):
            if multi:
                days, excluded, _ = build_route_days(req, data["legs"], data["back"], data["back_stops"], drop_count=attempt)
            else:
                days, excluded, _ = build_days(req, data["legs"][0]["route"], data["back"], data["legs"][0]["stops"], data["back_stops"],
                    data["legs"][0].get("attractions", []), data["legs"][0].get("food", []), drop_count=attempt)
            result = ItineraryVersion(version=state["version"], created_at=datetime.now(timezone.utc), status="ready",
                days=days, excluded=excluded, route=data["out"], route_alternatives=data["alternatives"],
                weather=data["weather"], advisories=data["advisories"], notes=notes,
                budget=build_budget(req, data["out"], data["back"], journey_km=journey_km))
            result.issues = feasibility.check(req, result)
            if not any(i.severity == "error" for i in result.issues):
                break
        if any(i.severity == "error" for i in result.issues) or data["incomplete"]:
            result.status = PlanStatus.partial
        return {"result": result}
