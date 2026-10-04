"""Version-safe delay changes, with explicit date rollover and constraint checks."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.models.itinerary import DayPlan, PlanStatus
from app.planner import feasibility


def apply_delay(req, version, delay_minutes, from_activity_id=None):
    result = version.model_copy(deep=True)
    active = from_activity_id is None
    grouped = defaultdict(list)
    for day in result.days:
        for activity in day.activities:
            if activity.id == from_activity_id:
                active = True
            if active and activity.status not in ("locked", "completed", "skipped"):
                start = datetime.combine(activity.day, activity.planned_start) + timedelta(minutes=delay_minutes)
                end = datetime.combine(activity.day, activity.planned_end) + timedelta(minutes=delay_minutes)
                activity.day = start.date()
                activity.planned_start, activity.planned_end = start.time(), end.time()
                if end.date() != start.date():
                    result.notes.append(f"{activity.name} crosses midnight; split/review this leg before travel.")
            grouped[activity.day].append(activity)
    result.days = [DayPlan(day=d, activities=sorted(acts, key=lambda a: a.planned_start))
                   for d, acts in sorted(grouped.items())]
    result.version += 1
    result.created_at = datetime.now(timezone.utc)
    result.notes.append(f"Shifted remaining unlocked activities by {delay_minutes} minutes; review conflicts below.")
    result.issues = feasibility.check(req, result)
    result.status = PlanStatus.partial if any(i.severity == "error" for i in result.issues) else PlanStatus.ready
    return result
