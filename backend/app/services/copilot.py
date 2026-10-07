"""Mistral-backed natural-language intake, bounded by the typed trip contract."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.models.trip import TripRequest

MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"
INTAKE_CACHE_TTL_SECONDS = 600

_intake_cache: dict[str, tuple[float, dict]] = {}
_intake_lock = threading.Lock()


def _cache_key(message: str) -> str:
    return hashlib.sha256(" ".join(message.strip().lower().split()).encode()).hexdigest()

TRIP_SCHEMA = """{"origin": "City", "destinations": ["Up to 4 cities in visit order"],
"start_date": "YYYY-MM-DD", "return_date": "YYYY-MM-DD", "departure_time": "HH:MM",
"return_deadline": "HH:MM", "transport_mode": "car or motorcycle",
"group": {"adults": 1, "group_type": "friends"},
"vehicles": [{"mode": "car or motorcycle", "count": 1, "mileage_km_per_litre": 40, "tank_litres": 12}],
"budget": {"per_person_inr": 5000}, "road": {"avoid_night_riding": true, "max_daily_drive_minutes": 420},
"food": {"vegetarian": true}, "must_visit": ["Place"], "pace": "relaxed, balanced or packed"}"""

SYSTEM_PROMPT = f"""You extract a road-trip draft for TripPilot India.
Return JSON only with exactly two keys: `trip` and `clarifications`.
`trip` must use EXACTLY these flat keys when the user supplied them, no nesting, no synonyms:
{TRIP_SCHEMA}.
Do not invent dates, locations, group size, vehicle details, money, or safety constraints.
TripPilot supports 1 to 4 Indian road destinations in visit order, plus cars or motorcycles.
When a required planning field is absent, leave it out and add one concise clarification.
Never claim a route, price, availability, booking, opening hour, or travel duration."""

CHAT_PROMPT = f"""You are TripPilot's vacation planner chat agent. Hold a short natural conversation
that collects a multi-stop road-trip intent: origin, destinations in visit order
(up to 4 Indian cities), dates, party, transport, budget and must-visit places.
Return JSON only with exactly three keys: `reply`, `trip`, `clarifications`.
`reply` is your next chat message (one short question, or a summary when the draft is complete).
Never state distances, durations, prices, availability or bookings in `reply`.
`trip` is your best-effort draft on EVERY turn: include every supplied field with
EXACTLY these flat keys, leave unknown fields out, never null once origin and at
least one destination are known:
{TRIP_SCHEMA}.
`clarifications` lists what is still missing. Never invent details, routes, prices or bookings."""


@dataclass
class IntakeResult:
    request: TripRequest | None
    clarifications: list[str]


@dataclass
class ConverseResult:
    reply: str
    request: TripRequest | None
    clarifications: list[str]


class MistralTripCopilot:
    def __init__(self) -> None:
        self.settings = get_settings()

    def intake(self, message: str) -> IntakeResult:
        payload = self._complete(message)
        clarifications = [str(item).strip() for item in payload.get("clarifications", []) if str(item).strip()]
        candidate = payload.get("trip")
        if not isinstance(candidate, dict):
            return IntakeResult(None, clarifications or ["Please provide your origin, destination, dates and group size."])
        try:
            return IntakeResult(TripRequest.model_validate(candidate), clarifications)
        except ValidationError as exc:
            missing = []
            for error in exc.errors():
                field = ".".join(str(part) for part in error["loc"])
                if field:
                    missing.append(f"Please confirm {field.replace('_', ' ')}.")
            return IntakeResult(None, clarifications + list(dict.fromkeys(missing)))

    def converse(self, messages: list[dict]) -> ConverseResult:
        """Multi-turn vacation planning chat. Returns the agent reply plus an
        optional validated multi-stop draft. The planner stays authoritative."""
        payload = self._chat(messages)
        reply = str(payload.get("reply") or "").strip() or "Tell me your origin, destinations, dates and group size."
        clarifications = [str(item).strip() for item in payload.get("clarifications", []) if str(item).strip()]
        candidate = payload.get("trip")
        if not isinstance(candidate, dict):
            return ConverseResult(reply, None, clarifications)
        try:
            return ConverseResult(reply, TripRequest.model_validate(candidate), clarifications)
        except ValidationError as exc:
            missing = []
            for error in exc.errors():
                field = ".".join(str(part) for part in error["loc"])
                if field:
                    missing.append(f"Please confirm {field.replace('_', ' ')}.")
            return ConverseResult(reply, None, clarifications + list(dict.fromkeys(missing)))

    def _chat(self, messages: list[dict]) -> dict:
        if not self.settings.llm_enabled:
            raise RuntimeError("Mistral copilot is unavailable. Add MISTRAL_API_KEY to backend/.env.")
        body = {
            "model": self.settings.mistral_model,
            "temperature": 0,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": CHAT_PROMPT}] + [
                {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:4000]}
                for m in messages[-20:]
            ],
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    MISTRAL_CHAT_URL,
                    headers={"Authorization": f"Bearer {self.settings.mistral_api_key}"},
                    json=body,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RuntimeError("Mistral quota is exhausted. Use the structured form or add quota, then try again.") from None
            raise RuntimeError("Mistral intake failed. Try again or use the structured form.") from None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Mistral intake failed. Try again or use the structured form.") from exc
        if not isinstance(content, str):
            raise RuntimeError("Mistral returned an unsupported intake response.")
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Mistral returned invalid intake JSON. Try again or use the structured form.") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Mistral returned an unsupported intake response.")
        return decoded

    def _complete(self, message: str) -> dict:
        if not self.settings.llm_enabled:
            raise RuntimeError("Mistral copilot is unavailable. Add MISTRAL_API_KEY to backend/.env.")
        key = _cache_key(message)
        with _intake_lock:
            cached = _intake_cache.get(key)
            if cached and cached[0] > time.time():
                return copy.deepcopy(cached[1])
            _intake_cache.pop(key, None)
        body = {
            "model": self.settings.mistral_model,
            "temperature": 0,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    MISTRAL_CHAT_URL,
                    headers={"Authorization": f"Bearer {self.settings.mistral_api_key}"},
                    json=body,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RuntimeError("Mistral quota is exhausted. Use the structured form or add quota, then try again.") from None
            raise RuntimeError("Mistral intake failed. Try again or use the structured form.") from None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Mistral intake failed. Try again or use the structured form.") from exc
        if not isinstance(content, str):
            raise RuntimeError("Mistral returned an unsupported intake response.")
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Mistral returned invalid intake JSON. Try again or use the structured form.") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Mistral returned an unsupported intake response.")
        with _intake_lock:
            _intake_cache[key] = (time.time() + INTAKE_CACHE_TTL_SECONDS, copy.deepcopy(decoded))
        return decoded
