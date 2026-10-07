import httpx
import json
import pytest

from app.config import get_settings
from app.services import copilot as copilot_module
from app.services.copilot import MistralTripCopilot


def test_copilot_returns_a_validated_road_trip_request(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    get_settings.cache_clear()
    copilot = MistralTripCopilot()
    monkeypatch.setattr(copilot, "_complete", lambda _: {
        "trip": {
            "origin": "Coimbatore",
            "destinations": ["Munnar"],
            "start_date": "2026-10-10",
            "return_date": "2026-10-11",
            "departure_time": "06:00",
            "return_deadline": "18:30",
            "transport_mode": "motorcycle",
            "group": {"adults": 6, "group_type": "friends"},
            "vehicles": [{"mode": "motorcycle", "count": 3, "mileage_km_per_litre": 40, "tank_litres": 12}],
            "budget": {"per_person_inr": 5000},
            "road": {"avoid_night_riding": True, "max_daily_drive_minutes": 420},
        },
        "clarifications": [],
    })

    result = copilot.intake("Six friends on three bikes from Coimbatore to Munnar next weekend")

    assert result.request is not None
    assert result.request.destinations == ["Munnar"]
    assert result.request.transport_mode == "motorcycle"
    assert result.clarifications == []


def test_copilot_refuses_to_plan_from_incomplete_model_output(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    get_settings.cache_clear()
    copilot = MistralTripCopilot()
    monkeypatch.setattr(copilot, "_complete", lambda _: {
        "trip": {"origin": "Coimbatore", "destinations": ["Munnar"]},
        "clarifications": ["What dates are you travelling?"],
    })

    result = copilot.intake("Plan a Munnar trip")

    assert result.request is None
    assert "What dates are you travelling?" in result.clarifications


def test_copilot_explains_when_mistral_quota_is_exhausted(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    get_settings.cache_clear()

    class QuotaClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *_args, **_kwargs):
            response = httpx.Response(429, request=httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions"))
            response.raise_for_status()

    monkeypatch.setattr("app.services.copilot.httpx.Client", lambda **_: QuotaClient())

    with pytest.raises(RuntimeError, match="quota"):
        MistralTripCopilot().intake("Plan a weekend road trip from Coimbatore to Munnar")


def test_copilot_serves_identical_intake_from_cache_without_a_second_call(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    get_settings.cache_clear()
    copilot_module._intake_cache.clear()
    calls = []
    draft = {
        "trip": {
            "origin": "Coimbatore",
            "destinations": ["Munnar"],
            "start_date": "2026-11-14",
            "return_date": "2026-11-15",
            "transport_mode": "motorcycle",
            "group": {"adults": 2},
        },
        "clarifications": [],
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(draft)}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            calls.append(1)
            return FakeResponse()

    monkeypatch.setattr("app.services.copilot.httpx.Client", FakeClient)
    copilot = MistralTripCopilot()
    first = copilot.intake("Cache probe: two adults ride Coimbatore to Munnar on 2026-11-14")
    second = copilot.intake("  CACHE PROBE: two adults ride Coimbatore to Munnar on 2026-11-14  ")

    assert first.request is not None and second.request is not None
    assert first.request.origin == second.request.origin == "Coimbatore"
    assert len(calls) == 1
