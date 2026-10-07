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


def test_two_destinations_are_accepted_and_more_than_four_rejected():
    assert request(destinations=["Munnar", "Thekkady"]).destinations == ["Munnar", "Thekkady"]
    with pytest.raises(ValueError):
        request(destinations=["A", "B", "C", "D", "E"])
    with pytest.raises(ValueError):
        request(destinations=["Munnar", "munnar "])


def test_multicity_pipeline_covers_each_city_with_checkin(monkeypatch):
    from app.models.itinerary import TravelMode
    from app.planner.pipeline import PlanningPipeline
    from app.services.maps import MapsService
    from app.services.search import SearchService
    from app.services.weather import WeatherService

    def fake_route(self, origin, destination, mode, name, avoid_tolls=False):
        leg = RouteLeg(id=name, from_name=origin, to_name=destination, distance_km=100,
                       duration_min=120, travel_mode="two_wheeler")
        best = RouteOption(id=name, label="Recommended route", legs=[leg],
                           total_distance_km=100, total_duration_min=120)
        alt_leg = RouteLeg(id=name + "-alt", from_name=origin, to_name=destination, distance_km=110,
                           duration_min=130, travel_mode="two_wheeler")
        alt = RouteOption(id=name + "-alt", label="Alternative route", legs=[alt_leg],
                          total_distance_km=110, total_duration_min=130)
        return best, [alt]

    monkeypatch.setattr(PlanningPipeline, "route", fake_route)
    monkeypatch.setattr(MapsService, "find_places", lambda *a, **k: [])
    monkeypatch.setattr(WeatherService, "forecast", lambda *a, **k: [])
    monkeypatch.setattr(SearchService, "advisories", lambda *a, **k: [])

    req = request(destinations=["Munnar", "Thekkady"], start_date="2026-11-10",
                  return_date="2026-11-13", road={"avoid_night_riding": False})
    result = PlanningPipeline().plan(req)
    names = [a.name for d in result.days for a in d.activities]
    assert "Check-in — Munnar" in names
    assert "Check-in — Thekkady" in names
    assert any("Thekkady" in note or "Munnar" in note for note in result.notes)
    assert all(i.severity != "error" for i in result.issues)


def test_route_option_selects_the_listed_alternative(monkeypatch):
    from app.planner.pipeline import PlanningPipeline
    from app.services.maps import MapsService
    from app.services.search import SearchService
    from app.services.weather import WeatherService

    def fake_route(self, origin, destination, mode, name, avoid_tolls=False):
        def option(label, km, mins):
            leg = RouteLeg(id=name + label, from_name=origin, to_name=destination, distance_km=km,
                           duration_min=mins, travel_mode="two_wheeler")
            return RouteOption(id=name + label, label=label, legs=[leg],
                               total_distance_km=km, total_duration_min=mins)
        return option("Recommended route", 100, 120), [option("Alternative route", 110, 130)]

    monkeypatch.setattr(PlanningPipeline, "route", fake_route)
    monkeypatch.setattr(MapsService, "find_places", lambda *a, **k: [])
    monkeypatch.setattr(WeatherService, "forecast", lambda *a, **k: [])
    monkeypatch.setattr(SearchService, "advisories", lambda *a, **k: [])

    result = PlanningPipeline().plan(request(), route_option=1)
    assert result.route.label == "Alternative route"
    assert result.route.total_distance_km == 110


def test_plan_endpoint_accepts_route_option(monkeypatch):
    monkeypatch.setenv("TRIPPILOT_FIXTURES", "1")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    client = TestClient(app)
    trip_id = client.post("/trips", json=request().model_dump(mode="json")).json()["id"]
    first = client.post(f"/trips/{trip_id}/plan", json={"route_option": 0}).json()["version"]
    assert first["route"]["label"] == "Recommended route"


def test_converse_returns_validated_multistop_draft(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    from app.services.copilot import MistralTripCopilot
    monkeypatch.setattr(MistralTripCopilot, "_chat", lambda self, messages: {
        "reply": "Got it! Any must-visit places?",
        "trip": {
            "origin": "Hyderabad",
            "destinations": ["Chennai", "Madurai"],
            "start_date": "2026-11-10",
            "return_date": "2026-11-19",
            "transport_mode": "car",
            "group": {"adults": 4},
        },
        "clarifications": ["What is your budget?"],
    })
    client = TestClient(app)
    body = client.post("/trips/converse", json={"messages": [
        {"role": "user", "content": "Family of 4 from Hyderabad, cover Chennai and Madurai in 10 days"}]}).json()
    assert body["request"]["destinations"] == ["Chennai", "Madurai"]
    assert "budget" in body["clarifications"][0].lower()


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
