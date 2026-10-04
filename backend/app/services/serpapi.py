"""SerpApi access layer: live calls, fixture fallback, budget, cache, evidence.

Fixture mode (no SERPAPI_API_KEY or TRIPPILOT_FIXTURES=1) serves recorded
responses from backend/fixtures/serpapi.json keyed by `fixture_key`.
Fixtures are clearly labelled in every SourceEvidence.note.
"""

from __future__ import annotations

import json
import threading
import copy
from urllib.parse import urlencode
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.models.itinerary import EvidenceKind, SourceEvidence
from app.services.cache import get_cache

FIXTURES_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "serpapi.json"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class SearchBudgetExceeded(RuntimeError):
    pass


class FixtureMiss(RuntimeError):
    pass


@dataclass
class ProviderResponse:
    engine: str
    data: dict[str, Any]
    retrieved_at: datetime
    fixture: bool
    sources: list[SourceEvidence] = field(default_factory=list)


class SearchBudget:
    """Hard cap on live+fixture searches per plan run."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0
        self._lock = threading.Lock()

    def consume(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise SearchBudgetExceeded(f"search budget of {self.limit} exceeded")
            self.used += 1


_fixtures_cache: Optional[dict[str, Any]] = None


def _load_fixtures() -> dict[str, Any]:
    global _fixtures_cache
    if _fixtures_cache is None:
        if FIXTURES_PATH.exists():
            _fixtures_cache = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        else:
            _fixtures_cache = {}
    return _fixtures_cache


class SerpApiService:
    def __init__(self, budget: Optional[SearchBudget] = None) -> None:
        self.settings = get_settings()
        self.budget = budget or SearchBudget(self.settings.trippilot_search_budget)
        self.cache = get_cache()

    def search(
        self,
        engine: str,
        params: dict[str, Any],
        fixture_key: Optional[str] = None,
    ) -> ProviderResponse:
        cache_key = f"serpapi:{self.settings.fixture_mode}:{engine}:{json.dumps(params, sort_keys=True)}:{fixture_key}"
        cached = self.cache.get(cache_key)
        if cached:
            return ProviderResponse(
                engine=engine,
                data=cached,
                retrieved_at=datetime.fromisoformat(cached["_retrieved_at"]),
                fixture=cached.get("_fixture", False),
                sources=[self._source(engine, cached.get("_search_url"), cached.get("_fixture", False),
                    datetime.fromisoformat(cached["_retrieved_at"]))],
            )

        self.budget.consume()
        if self.settings.fixture_mode:
            data = self._fixture(engine, fixture_key)
            fixture = True
        else:
            data = self._live(engine, params)
            fixture = False

        retrieved = datetime.now(timezone.utc)
        data["_retrieved_at"] = retrieved.isoformat()
        data["_fixture"] = fixture
        data["_search_url"] = self._search_url(engine, params)
        self.cache.set(cache_key, data)
        return ProviderResponse(
            engine=engine,
            data=data,
            retrieved_at=retrieved,
            fixture=fixture,
            sources=[self._source(engine, self._search_url(engine, params), fixture)],
        )

    def _live(self, engine: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {"engine": engine, "api_key": self.settings.serpapi_api_key, **params}
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.get(SERPAPI_ENDPOINT, params=query)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError:
            raise RuntimeError(f"SerpApi request failed for {engine}; check backend credentials and connectivity") from None
        if "error" in payload:
            raise RuntimeError(f"SerpApi error for {engine}: {payload['error']}")
        return payload

    def _fixture(self, engine: str, fixture_key: Optional[str]) -> dict[str, Any]:
        fixtures = _load_fixtures()
        if not fixture_key or fixture_key not in fixtures:
            raise FixtureMiss(
                f"no fixture for engine={engine} key={fixture_key}; "
                "record it in backend/fixtures/serpapi.json"
            )
        entry = fixtures[fixture_key]
        if isinstance(entry, dict) and entry.get("_engine") and entry["_engine"] != engine:
            raise FixtureMiss(f"fixture {fixture_key} belongs to {entry['_engine']}, not {engine}")
        return copy.deepcopy(entry.get("response", entry) if isinstance(entry, dict) else entry)

    @staticmethod
    def _search_url(engine: str, params: dict[str, Any]) -> str:
        qs = urlencode({k: v for k, v in params.items() if k != "api_key"})
        return f"{SERPAPI_ENDPOINT}?engine={engine}&{qs}"

    @staticmethod
    def _source(engine: str, url: Optional[str], fixture: bool, retrieved_at=None) -> SourceEvidence:
        return SourceEvidence(
            kind=EvidenceKind.retrieved,
            engine=engine,
            url=url,
            title=f"SerpApi {engine}",
            retrieved_at=retrieved_at or datetime.now(timezone.utc),
            note="Synthetic fixture; not a live or recorded provider result" if fixture else None,
        )
