"""Google Maps Directions (SerpApi): driving and two-wheeler route legs."""

from __future__ import annotations
from urllib.parse import urlencode

from app.models.itinerary import (
    GeoPoint,
    RouteLeg,
    RouteOption,
    RouteStep,
    SourceEvidence,
    TravelMode,
)
from app.services.serpapi import ProviderResponse, SerpApiService

_TRAVEL_MODE_PARAM = {
    TravelMode.driving: "0",
    TravelMode.two_wheeler: "9",
}


def _navigation_url(origin: str, destination: str, mode: TravelMode) -> str:
    return "https://www.google.com/maps/dir/?" + urlencode({"api": 1, "origin": origin,
        "destination": destination, "travelmode": "driving"})


def _point_from(name: str, data: dict) -> GeoPoint | None:
    for place in data.get("places_info", []) or []:
        if place.get("gps_coordinates"):
            c = place["gps_coordinates"]
            return GeoPoint(lat=c["latitude"], lng=c["longitude"])
    return None


def parse_leg(
    resp: ProviderResponse,
    leg_id: str,
    from_name: str,
    to_name: str,
    mode: TravelMode,
    route_index: int = 0,
) -> RouteLeg:
    directions = resp.data.get("directions") or []
    if not directions:
        raise ValueError("Provider returned no route for this leg")
    route = directions[min(route_index, len(directions) - 1)]
    step_titles: list[str] = []
    step_models: list[RouteStep] = []
    for trip in route.get("trips") or []:
        for detail in trip.get("details") or []:
            title = (detail.get("title") or "").strip()
            if not title:
                continue
            step_titles.append(title)
            coords = detail.get("gps_coordinates") or {}
            step_models.append(
                RouteStep(
                    title=title,
                    distance_m=detail.get("distance"),
                    duration_s=detail.get("duration"),
                    gps_coordinates=(
                        GeoPoint(lat=coords["latitude"], lng=coords["longitude"]) if coords else None
                    ),
                )
            )
    summary = " → ".join(step_titles[:6]) if step_titles else (route.get("via") or "")
    if len(step_titles) > 6:
        summary += " → …"

    return RouteLeg(
        id=leg_id,
        from_name=from_name,
        to_name=to_name,
        from_point=_point_from(from_name, resp.data),
        to_point=(GeoPoint(lat=resp.data["places_info"][-1]["gps_coordinates"]["latitude"],
            lng=resp.data["places_info"][-1]["gps_coordinates"]["longitude"])
            if resp.data.get("places_info") and resp.data["places_info"][-1].get("gps_coordinates") else None),
        distance_km=round((route.get("distance") or 0) / 1000, 1),
        duration_min=max(1, round((route.get("duration") or 0) / 60)),
        travel_mode=mode,
        summary=summary or None,
        navigation_url=_navigation_url(from_name, to_name, mode),
        steps=step_models,
        sources=resp.sources,
    )


def build_route_option(
    legs: list[RouteLeg],
    option_id: str,
    label: str,
) -> RouteOption:
    return RouteOption(
        id=option_id,
        label=label,
        legs=legs,
        total_distance_km=round(sum(l.distance_km for l in legs), 1),
        total_duration_min=sum(l.duration_min for l in legs),
        sources=[s for leg in legs for s in leg.sources],
    )


class DirectionsService:
    def __init__(self, serpapi: SerpApiService) -> None:
        self.serpapi = serpapi

    def get_leg(
        self,
        origin: str,
        destination: str,
        mode: TravelMode,
        leg_id: str,
        fixture_key: str,
        avoid: str | None = None,
    ) -> RouteLeg:
        params: dict = {
            "start_addr": origin,
            "end_addr": destination,
            "travel_mode": _TRAVEL_MODE_PARAM[mode],
            "distance_unit": "0",
            "gl": "in",
            "hl": "en",
        }
        if avoid:
            params["avoid"] = avoid
        resp = self.serpapi.search("google_maps_directions", params, fixture_key=fixture_key)
        return parse_leg(resp, leg_id, origin, destination, mode)
