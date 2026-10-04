"""Google Maps places (SerpApi): attractions, food, fuel, washrooms, stays."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import time as dtime
from typing import Optional
from urllib.parse import urlencode

from app.models.itinerary import (
    EvidenceKind,
    GeoPoint,
    OpeningHours,
    PlaceCandidate,
    PlaceCategory,
    SourceEvidence,
)
from app.services.serpapi import ProviderResponse, SerpApiService

_CATEGORY_QUERY = {
    PlaceCategory.attraction: "tourist attractions",
    PlaceCategory.restaurant: "vegetarian restaurants",
    PlaceCategory.fuel: "fuel petrol pump",
    PlaceCategory.washroom: "public restroom",
    PlaceCategory.rest: "rest stop cafe",
    PlaceCategory.accommodation: "hotels",
}


def _place_id(raw: str) -> str:
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _parse_clock(text: str) -> Optional[dtime]:
    """Parse '5 PM', '17:00', '6:30 am' into a time."""
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text.strip(), re.I)
    if not m:
        return None
    h, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    if h > 23 or minute > 59:
        return None
    return dtime(h, minute)


def _opening_hours(item: dict, resp: ProviderResponse) -> Optional[OpeningHours]:
    """Structured hours when the provider returns them, else parse open_state text."""
    evidence = SourceEvidence(
        kind=EvidenceKind.retrieved,
        engine=resp.engine,
        title=item.get("title"),
        retrieved_at=resp.retrieved_at,
        note="fixture response" if resp.fixture else "parsed from provider listing text",
    )
    oh = item.get("opening_hours")
    weekly = item.get("operating_hours")
    if isinstance(weekly, dict):
        return OpeningHours(weekly={k.lower(): v for k, v in weekly.items() if isinstance(v, str)},
                            raw=json.dumps(weekly), source=evidence)
    if isinstance(oh, dict) and (oh.get("open") or oh.get("close")):
        return OpeningHours(
            weekday_open=_parse_clock(str(oh.get("open", ""))),
            weekday_close=_parse_clock(str(oh.get("close", ""))),
            sunday_open=_parse_clock(str(oh.get("sunday_open", ""))),
            sunday_close=_parse_clock(str(oh.get("sunday_close", ""))),
            raw=json.dumps(oh),
            source=evidence,
        )
    text = item.get("open_state") or ""
    if not isinstance(text, str) or not text:
        return None
    return OpeningHours(raw=text, source=evidence)


def parse_places(
    resp: ProviderResponse,
    category: PlaceCategory,
    default_visit_minutes: int | None = None,
) -> list[PlaceCandidate]:
    results = resp.data.get("local_results") or resp.data.get("places") or []
    if not results and isinstance(resp.data.get("place_results"), dict):
        results = [resp.data["place_results"]]
    places: list[PlaceCandidate] = []
    for item in results:
        coords = item.get("gps_coordinates") or {}
        location = (GeoPoint(lat=coords["latitude"], lng=coords["longitude"])
                    if coords.get("latitude") is not None and coords.get("longitude") is not None else None)
        hours_raw = item.get("open_state") or item.get("hours")
        sources = list(resp.sources)
        if item.get("title"):
            sources.append(
                SourceEvidence(
                    kind=EvidenceKind.retrieved,
                    engine=resp.engine,
                    url="https://www.google.com/maps/search/?" + urlencode({"api": 1,
                        "query": item["title"], **({"query_place_id": item["place_id"]} if item.get("place_id") else {})}),
                    title=item.get("title"),
                    retrieved_at=resp.retrieved_at,
                    note="fixture response" if resp.fixture else None,
                )
            )
        places.append(
            PlaceCandidate(
                id=_place_id(item.get("data_id") or item.get("title") or item.get("link", "")),
                name=item.get("title") or "Unnamed place",
                category=category,
                address=item.get("address"),
                location=location,
                opening_hours=_opening_hours(item, resp),
                rating=item.get("rating"),
                price_level=item.get("price") if isinstance(item.get("price"), int) else None,
                estimated_visit_minutes=default_visit_minutes,
                notes=hours_raw if isinstance(hours_raw, str) else None,
                sources=sources,
            )
        )
    return places


class MapsService:
    def __init__(self, serpapi: SerpApiService) -> None:
        self.serpapi = serpapi

    def find_places(
        self,
        query: str,
        category: PlaceCategory,
        fixture_key: str,
        near: GeoPoint | None = None,
        visit_minutes: int | None = None,
        extra_query: str | None = None,
    ) -> list[PlaceCandidate]:
        full_query = " ".join(filter(None, [query, extra_query]))
        params: dict = {"q": full_query, "type": "search", "gl": "in", "hl": "en"}
        if near:
            params["ll"] = f"@{near.lat},{near.lng},14z"
        resp = self.serpapi.search("google_maps", params, fixture_key=fixture_key)
        return parse_places(resp, category, default_visit_minutes=visit_minutes)
