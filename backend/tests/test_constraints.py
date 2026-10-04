from datetime import time
from test_planner import request, itinerary, route
from app.planner.feasibility import check
from app.planner.replan import apply_delay
from app.planner.scheduler import build_budget
from app.planner.pipeline import PlanningPipeline
from app.services.serpapi import SearchBudget
from app.models.itinerary import PlaceCandidate, OpeningHours


def test_per_person_budget_with_room_to_spare():
    assert build_budget(request(budget={"per_person_inr": 1500}), route(), route()).within_budget


def test_locked_activity_does_not_shift():
    old = itinerary()
    old.days[0].activities[0].status = "locked"
    new = apply_delay(request(), old, 90)
    assert new.days[0].activities[0].planned_start == time(23)


def test_daily_limit_violation_is_explicit():
    old = itinerary()
    old.days[0].activities[0].planned_start = time(12)
    assert "daily_drive_exceeded" in [i.code for i in check(request(), old)]


def test_budget_exhaustion_produces_clear_failure(monkeypatch):
    monkeypatch.setenv("TRIPPILOT_FIXTURES", "1")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.services.cache import get_cache
    get_cache()._mem.clear()
    result = PlanningPipeline(SearchBudget(0)).plan(request())
    assert result.status == "failed"
    assert result.issues[0].code == "provider_unavailable"


def test_closed_attraction_and_missing_hours_are_flagged():
    old = itinerary()
    activity = old.days[0].activities[0]
    activity.type = "attraction"
    activity.planned_start, activity.planned_end = time(8), time(9)
    activity.place = PlaceCandidate(id="a", name="Museum", category="attraction",
        opening_hours=OpeningHours(weekday_open=time(10), weekday_close=time(17)))
    assert "closed_at_arrival" in [i.code for i in check(request(), old)]
    activity.place.opening_hours = None
    assert "opening_hours_unknown" in [i.code for i in check(request(), old)]


def test_missing_must_visit_remains_an_explicit_conflict():
    assert "must_visit_not_scheduled" in [i.code for i in check(request(must_visit=["Unknown attraction"]), itinerary())]


def test_night_travel_is_not_accepted():
    assert "night_driving" in [i.code for i in check(request(), itinerary())]


def test_editing_creates_a_new_version_and_rechecks_must_visit(monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import get_settings
    monkeypatch.setenv("TRIPPILOT_FIXTURES", "1")
    get_settings.cache_clear()
    from app.main import app
    from app.services.store import get_store
    client = TestClient(app)
    req = request(must_visit=["Tea Museum"])
    trip_id = client.post("/trips", json=req.model_dump(mode="json")).json()["id"]
    old = client.post(f"/trips/{trip_id}/plan").json()["version"]
    activity = next(a for d in old["days"] for a in d["activities"] if a["name"] == "Tea Museum")
    new = client.patch(f"/trips/{trip_id}/activities/{activity['id']}", json={"status": "skipped"}).json()["version"]
    assert new["version"] == 2
    assert new["status"] == "partial"
    original = get_store().get(trip_id).versions[0]
    assert all(a.status != "skipped" for d in original.days for a in d.activities)
