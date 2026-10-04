from datetime import date, datetime, time, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.trip import TripRequest
from app.models.itinerary import Activity, DayPlan, ItineraryVersion, RouteLeg, RouteOption
from app.planner.replan import apply_delay
from app.planner.scheduler import build_budget
from app.services.serpapi import ProviderResponse
from app.services.directions import parse_leg


def request(**updates):
    data = dict(origin="Coimbatore", destinations=["Munnar"], start_date="2026-10-10",
                return_date="2026-10-11", return_deadline="18:30", transport_mode="motorcycle",
                group={"adults": 6}, vehicles=[{"mode": "motorcycle", "count": 3,
                    "mileage_km_per_litre": 40, "tank_litres": 12}],
                road={"avoid_night_riding": True}, budget={"per_person_inr": 5000})
    return TripRequest(**(data | updates))


def route():
    leg = RouteLeg(id="r", from_name="A", to_name="B", distance_km=140,
                   duration_min=240, travel_mode="two_wheeler")
    return RouteOption(id="r", label="Route", legs=[leg], total_distance_km=140,
                       total_duration_min=240)


def itinerary():
    activity = Activity(id="a", type="drive", name="Drive", day=date(2026, 10, 10),
                        planned_start=time(23), planned_end=time(23, 30))
    return ItineraryVersion(version=1, created_at=datetime.now(timezone.utc), status="ready",
                            days=[DayPlan(day=activity.day, activities=[activity])])


def test_multivehicle_fuel_cost_includes_every_bike():
    fuel = build_budget(request(), route(), route()).lines[0]
    assert fuel.amount_inr == round(280 / 40 * 102 * 3)


def test_per_person_budget_is_not_compared_with_group_total():
    req = request(budget={"per_person_inr": 1200})
    assert build_budget(req, route(), route()).within_budget is False


def test_replanning_preserves_prior_version_and_midnight_date():
    old = itinerary()
    new = apply_delay(request(), old, 90)
    assert old.days[0].activities[0].planned_start == time(23)
    assert new.days[0].activities[0].day == date(2026, 10, 11)
    assert new.days[0].activities[0].planned_start == time(0, 30)


def test_missing_route_is_not_a_zero_minute_success():
    resp = ProviderResponse("google_maps_directions", {}, datetime.now(timezone.utc), True)
    with pytest.raises(ValueError):
        parse_leg(resp, "x", "A", "B", "two_wheeler")


def test_supported_timezone_and_transport_validation():
    with pytest.raises(ValueError):
        request(timezone="Mars/Unknown")
    with pytest.raises(ValueError):
        request(transport_mode="train")


def test_fixture_trip_end_to_end(monkeypatch):
    monkeypatch.setenv("TRIPPILOT_FIXTURES", "1")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    client = TestClient(app)
    created = client.post("/trips", json=request().model_dump(mode="json"))
    assert created.status_code == 201
    trip_id = created.json()["id"]
    plan = client.post(f"/trips/{trip_id}/plan")
    assert plan.status_code == 200
    version = plan.json()["version"]
    assert version["status"] == "ready"
    assert len(version["days"]) == 2
    assert any("synthetic" in note.lower() for note in version["notes"])
    assert version["days"][-1]["activities"][-1]["type"] == "drive"
    assert all(i["severity"] != "error" for i in version["issues"])
    # Every displayed stop uses its actual schedule, not unadjusted provider times.
    for day in version["days"]:
        for prev, nxt in zip(day["activities"], day["activities"][1:]):
            assert prev["planned_end"] <= nxt["planned_start"]
    shared = client.post(f"/trips/{trip_id}/share").json()["share_url"]
    assert client.get(shared).status_code == 200
    assert "id" not in client.get(shared).json()  # read-only recipients must not receive the private edit identifier


def test_fixture_cache_never_serves_synthetic_data_in_live_mode(monkeypatch):
    from app.config import get_settings
    from app.services.serpapi import SerpApiService
    monkeypatch.setenv("TRIPPILOT_FIXTURES", "1")
    get_settings.cache_clear()
    synthetic = SerpApiService()
    synthetic.search("google_maps", {"q": "Munnar"}, "places:munnar:attractions")
    monkeypatch.setenv("TRIPPILOT_FIXTURES", "0")
    monkeypatch.setenv("SERPAPI_API_KEY", "test-value-not-a-credential")
    get_settings.cache_clear()
    live = SerpApiService()
    monkeypatch.setattr(live, "_live", lambda *args: {"local_results": [], "live": True})
    assert live.search("google_maps", {"q": "Munnar"}, "places:munnar:attractions").data["live"]
    get_settings.cache_clear()
