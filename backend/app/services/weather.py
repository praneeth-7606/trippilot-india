"""Open-Meteo forecasts (free, no key) with fixture fallback for tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings
from app.models.itinerary import EvidenceKind, SourceEvidence, WeatherDay

FIXTURES_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo.json"

_WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 61: "Light rain",
    63: "Rain", 65: "Heavy rain", 71: "Light snow", 80: "Rain showers",
    81: "Rain showers", 82: "Violent rain showers", 95: "Thunderstorm",
}


def _source(url: str, fixture: bool) -> SourceEvidence:
    return SourceEvidence(
        kind=EvidenceKind.retrieved,
        engine="open-meteo",
        url=url,
        title="Open-Meteo forecast",
        retrieved_at=datetime.now(timezone.utc),
        note="Synthetic weather fixture, not an actual forecast" if fixture else None,
    )


class WeatherService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def forecast(
        self,
        lat: float,
        lng: float,
        days: list,
        fixture_key: Optional[str] = None,
    ) -> list[WeatherDay]:
        if self.settings.fixture_mode:
            return self._fixture(fixture_key, days)

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lng}"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            "&forecast_days=16&timezone=Asia%2FKolkata"
        )
        try:
            with httpx.Client(timeout=15.0) as client:
                payload = client.get(url).json()
        except Exception:
            return [
                WeatherDay(day=d, summary="Forecast unavailable", sources=[_source(url, False)])
                for d in days
            ]

        daily = payload.get("daily", {})
        by_date = {}
        for i, ds in enumerate(daily.get("time", [])):
            by_date[ds] = i

        out: list[WeatherDay] = []
        for day in days:
            i = by_date.get(day.isoformat())
            if i is None:
                out.append(
                    WeatherDay(day=day, summary="Forecast unavailable (beyond 16 days)",
                               sources=[_source(url, False)])
                )
                continue
            code = daily.get("weather_code", [None])[i]
            out.append(
                WeatherDay(
                    day=day,
                    summary=_WMO.get(code, f"Weather code {code}"),
                    max_c=daily.get("temperature_2m_max", [None])[i],
                    min_c=daily.get("temperature_2m_min", [None])[i],
                    precipitation_probability=daily.get("precipitation_probability_max", [None])[i],
                    sources=[_source(url, False)],
                )
            )
        return out

    def _fixture(self, fixture_key: Optional[str], days: list) -> list[WeatherDay]:
        if not FIXTURES_PATH.exists():
            return [WeatherDay(day=d, summary="Fixture missing") for d in days]
        data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        rows = data.get(fixture_key or "", [])
        out = []
        for i, day in enumerate(days):
            row = rows[i] if i < len(rows) else None
            out.append(
                WeatherDay(
                    day=day,
                    summary=row.get("summary") if row else "Forecast unavailable",
                    max_c=row.get("max_c") if row else None,
                    min_c=row.get("min_c") if row else None,
                    precipitation_probability=row.get("precip") if row else None,
                    sources=[_source("https://api.open-meteo.com/v1/forecast", True)],
                )
            )
        return out
