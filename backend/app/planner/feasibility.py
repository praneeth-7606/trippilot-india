"""Feasibility checks: what makes an itinerary impossible or risky."""

from __future__ import annotations

from app.models.itinerary import (
    Activity,
    ActivityType,
    FeasibilityIssue,
    FeasibilitySeverity,
    ItineraryVersion,
)
from app.models.trip import TripRequest
from app.planner.timeutil import minutes_of


def _overlaps(a: Activity, b: Activity) -> bool:
    return minutes_of(a.planned_start) < minutes_of(b.planned_end) and minutes_of(
        b.planned_start
    ) < minutes_of(a.planned_end)


def check(req: TripRequest, itinerary: ItineraryVersion) -> list[FeasibilityIssue]:
    issues: list[FeasibilityIssue] = []

    # Chronological order inside each day.
    for day in itinerary.days:
        acts = [a for a in day.activities if a.type != ActivityType.free and a.status != "skipped"]
        for a in acts:
            if a.planned_end <= a.planned_start:
                issues.append(FeasibilityIssue(code="midnight_or_invalid_duration", severity="error",
                    message=f"{a.name} crosses midnight or has an invalid duration; split/review this activity.", related_activity_ids=[a.id]))
        for prev, nxt in zip(acts, acts[1:]):
            if minutes_of(nxt.planned_start) < minutes_of(prev.planned_end):
                issues.append(FeasibilityIssue(
                    code="overlap",
                    severity=FeasibilitySeverity.error,
                    message=f"{nxt.name} starts before {prev.name} ends on {day.day}.",
                    related_activity_ids=[prev.id, nxt.id],
                ))
            elif _overlaps(prev, nxt):
                issues.append(FeasibilityIssue(
                    code="overlap",
                    severity=FeasibilitySeverity.error,
                    message=f"{nxt.name} overlaps {prev.name} on {day.day}.",
                    related_activity_ids=[prev.id, nxt.id],
                ))

    # Daily driving limit.
    per_day_drive: dict = {}
    for day in itinerary.days:
        total = sum(
            (minutes_of(a.planned_end) - minutes_of(a.planned_start))
            for a in day.activities if a.type == ActivityType.drive
        )
        per_day_drive[day.day] = total
        if total > req.road.max_daily_drive_minutes:
            issues.append(FeasibilityIssue(
                code="daily_drive_exceeded",
                severity=FeasibilitySeverity.error,
                message=(
                    f"{day.day} has {total} min of driving; limit is "
                    f"{req.road.max_daily_drive_minutes} min."
                ),
            ))

    # Night riding rule.
    if req.road.avoid_night_riding:
        cutoff = minutes_of(req.road.night_cutoff)
        for day in itinerary.days:
            for a in day.activities:
                if a.type == ActivityType.drive and minutes_of(a.planned_end) > cutoff:
                    issues.append(FeasibilityIssue(
                        code="night_driving",
                        severity=FeasibilitySeverity.error,
                        message=f"{a.name} ends after {req.road.night_cutoff.strftime('%H:%M')} "
                                "but night travel was ruled out.",
                        related_activity_ids=[a.id],
                    ))

    # Must-visits are never removed without an explicit conflict.
    scheduled = [a.name.lower() for d in itinerary.days for a in d.activities if a.status != "skipped"]
    for name in req.must_visit:
        if not any(name.lower() in s for s in scheduled):
            issues.append(FeasibilityIssue(code="must_visit_not_scheduled", severity="error",
                message=f"Must-visit '{name}' could not be scheduled. Extend the trip or explicitly change this requirement."))

    # Return deadline.
    if req.return_deadline and itinerary.days:
        last_day = itinerary.days[-1]
        drives = [a for a in last_day.activities if a.type == ActivityType.drive]
        if drives:
            final_arrival = minutes_of(drives[-1].planned_end)
            deadline = minutes_of(req.return_deadline)
            if final_arrival > deadline:
                issues.append(FeasibilityIssue(
                    code="return_deadline_missed",
                    severity=FeasibilitySeverity.error,
                    message=(
                        f"Return leg ends at {drives[-1].planned_end.strftime('%H:%M')}, "
                        f"after the {req.return_deadline.strftime('%H:%M')} deadline."
                    ),
                    related_activity_ids=[drives[-1].id],
                ))
        if req.return_date and last_day.day > req.return_date:
            issues.append(FeasibilityIssue(code="return_date_missed", severity="error",
                message="Delay moves part of the itinerary beyond the requested return date."))

    # Opening hours when published.
    for day in itinerary.days:
        for a in day.activities:
            if a.type != ActivityType.attraction or not a.place:
                continue
            hours = a.place.opening_hours
            if not hours or (hours.weekday_open is None and hours.weekday_close is None):
                issues.append(FeasibilityIssue(
                    code="opening_hours_unknown",
                    severity=FeasibilitySeverity.warning,
                    message=f"No published hours found for {a.name}; confirm before visiting.",
                    related_activity_ids=[a.id],
                ))
                continue
            if hours.weekday_open and minutes_of(a.planned_start) < minutes_of(hours.weekday_open):
                issues.append(FeasibilityIssue(
                    code="closed_at_arrival",
                    severity=FeasibilitySeverity.error,
                    message=(
                        f"{a.name} opens at {hours.weekday_open.strftime('%H:%M')} but the plan "
                        f"arrives at {a.planned_start.strftime('%H:%M')}."
                    ),
                    related_activity_ids=[a.id],
                ))
            if hours.weekday_close and minutes_of(a.planned_end) > minutes_of(hours.weekday_close):
                issues.append(FeasibilityIssue(
                    code="closed_during_visit",
                    severity=FeasibilitySeverity.warning,
                    message=(
                        f"{a.name} closes at {hours.weekday_close.strftime('%H:%M')} but the plan "
                        f"leaves at {a.planned_end.strftime('%H:%M')}."
                    ),
                    related_activity_ids=[a.id],
                ))

    # Budget.
    budget_limit = req.budget.total_inr or (req.budget.per_person_inr * req.group.total if req.budget.per_person_inr else None)
    if budget_limit and itinerary.budget:
        if itinerary.budget.total_inr > budget_limit:
            issues.append(FeasibilityIssue(
                code="budget_exceeded",
                severity=FeasibilitySeverity.warning,
                message=(
                    f"Estimated ₹{itinerary.budget.total_inr:,} exceeds the "
                    f"₹{budget_limit:,} budget."
                ),
            ))

    return issues
