"""Google Search (SerpApi): official pages, attraction rules, advisories."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.itinerary import Advisory
from app.services.serpapi import SerpApiService


class SearchService:
    def __init__(self, serpapi: SerpApiService) -> None:
        self.serpapi = serpapi

    def advisories(self, query: str, fixture_key: str, limit: int = 4) -> list[Advisory]:
        resp = self.serpapi.search(
            "google",
            {"q": query, "gl": "in", "hl": "en", "num": limit},
            fixture_key=fixture_key,
        )
        out: list[Advisory] = []
        for item in (resp.data.get("organic_results") or [])[:limit]:
            link = item.get("link") or ""
            if not link:
                continue
            out.append(Advisory(
                text=(item.get("snippet") or item.get("title") or "")[:300],
                url=link,
                retrieved_at=resp.retrieved_at or datetime.now(timezone.utc),
            ))
        return out
