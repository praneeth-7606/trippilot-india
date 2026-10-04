"""Run the actual planning workflow once; export only its public-safe typed plan.

Run from backend/. Credentials stay in .env; never print provider request URLs
or tracebacks. The output directory is gitignored.
"""
import json
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.models.trip import TripRequest
from app.planner.pipeline import PlanningPipeline


def main():
    settings = get_settings()
    if not settings.serpapi_api_key.strip() or settings.fixture_mode:
        print("Live verification requires a local key and TRIPPILOT_FIXTURES=0.")
        return 1
    request = TripRequest(origin="Coimbatore", destinations=["Munnar"],
        start_date="2026-10-10", return_date="2026-10-11", departure_time="06:00",
        return_deadline="18:30", transport_mode="motorcycle", group={"adults": 6},
        vehicles=[{"mode": "motorcycle", "count": 3, "mileage_km_per_litre": 40, "tank_litres": 12}],
        food={"vegetarian": True}, budget={"per_person_inr": 5000},
        road={"avoid_night_riding": True, "max_daily_drive_minutes": 420},
        must_visit=["Tea Museum", "Mattupetty Dam"])
    pipeline = PlanningPipeline()
    try:
        plan = pipeline.plan(request)
    except Exception as error:
        print(json.dumps({"verification": "failed", "error_type": type(error).__name__}))
        return 1
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    typed = plan.model_dump(mode="json")
    serialized = json.dumps(typed, indent=2)
    # Defence in depth: forbid the actual credential in any export.
    if settings.serpapi_api_key in serialized:
        print("Export refused: credential detected in plan output.")
        return 1
    (out / "live-plan.json").write_text(serialized, encoding="utf-8")
    activities = [a for d in plan.days for a in d.activities]
    summary = {"fixture_mode": False, "status": plan.status.value,
        "searches": pipeline.budget.used,
        "outbound_km": plan.route.total_distance_km if plan.route else None,
        "outbound_minutes": plan.route.total_duration_min if plan.route else None,
        "days": len(plan.days), "activities": dict(Counter(a.type.value for a in activities)),
        "issues": [{"code": i.code, "severity": i.severity.value, "message": i.message} for i in plan.issues],
        "notes": plan.notes, "export": "backend/data/live-plan.json"}
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if plan.status.value != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
