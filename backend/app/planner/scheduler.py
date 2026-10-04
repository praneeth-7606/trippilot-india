"""Deterministic itinerary construction: days, timeline, attraction grouping.

The LLM does not schedule anything — this module applies the scheduling rules
from SPEC.md so results are reproducible and testable.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Optional

from app.models.itinerary import (
    Activity,
    ActivityStatus,
    ActivityType,
    BudgetLine,
    BudgetSummary,
    DayPlan,
    EvidenceKind,
    ExcludedActivity,
    PlaceCandidate,
    PlaceCategory,
    RouteOption,
    SourceEvidence,
)
from app.models.trip import TravelPace, TripRequest
from app.planner.stops import StopPlan
from app.planner.timeutil import at, haversine_km, minutes_of, time_of

PACE_DAILY_VISIT_MINUTES = {
    TravelPace.relaxed: 240,
    TravelPace.balanced: 330,
    TravelPace.packed: 420,
}

EVENING_CUTOFF = 18 * 60 + 30   # stop starting new activities after this
MORNING_START = 8 * 60 + 30
CHECKIN_MINUTES = 20
MIN_ATTRACTION_WINDOW = 150     # minutes needed on day 1 to bother scheduling any
FUEL_PRICE_INR_PER_L = 102      # assumption, surfaced in cost basis
FOOD_INR_PER_PERSON_DAY = 500   # assumption, surfaced in cost basis


def _id(name: str, day: date, idx: int) -> str:
    return hashlib.sha1(f"{name}:{day}:{idx}".encode()).hexdigest()[:10]


def _calculated_source(note: str) -> SourceEvidence:
    from datetime import timezone

    return SourceEvidence(
        kind=EvidenceKind.calculated,
        engine=None,
        url=None,
        title="TripPilot estimate",
        retrieved_at=datetime.now(timezone.utc),
        note=note,
    )


def intra_city_minutes(a: PlaceCandidate, b: PlaceCandidate) -> int:
    """Straight-line estimate for city hops; labelled as calculated."""
    if not a.location or not b.location:
        return 15
    km = haversine_km((a.location.lat, a.location.lng), (b.location.lat, b.location.lng)) * 1.4
    return max(8, round(km / 25 * 60))  # ~25 km/h average in town


def _drive_activity(name: str, day: date, start: datetime, end: datetime,
                    sources: list[SourceEvidence], idx: int) -> Activity:
    return Activity(
        id=_id(name, day, idx),
        type=ActivityType.drive,
        name=name,
        day=day,
        planned_start=start.timetz().replace(tzinfo=None),
        planned_end=end.timetz().replace(tzinfo=None),
        status=ActivityStatus.planned,
        sources=sources,
        explanation=f"Driving segment with {len(sources)} route source(s).",
    )


def _stop_activity(stop: StopPlan, day: date, idx: int) -> Activity:
    return Activity(
        id=_id(stop.place.name, day, idx),
        type={
            "restaurant": ActivityType.meal,
            "fuel": ActivityType.fuel,
            "washroom": ActivityType.washroom,
            "rest": ActivityType.rest,
        }.get(stop.category.value, ActivityType.free),
        name=stop.place.name,
        day=day,
        planned_start=stop.arrive_at.timetz().replace(tzinfo=None),
        planned_end=stop.depart_at.timetz().replace(tzinfo=None),
        place=stop.place,
        status=ActivityStatus.planned,
        explanation=stop.reason,
        sources=stop.place.sources,
    )


def _travel_day(
    req: TripRequest,
    day: date,
    departure: datetime,
    route: RouteOption,
    stops: list[StopPlan],
    drive_name: str,
) -> tuple[list[Activity], datetime]:
    """Timeline for one driving day: departure, stops, arrival. Returns (acts, arrival)."""
    acts: list[Activity] = []
    idx = 0
    cursor = departure
    dwell_so_far = 0
    detours_so_far = 0

    for stop in stops:
        arrive = departure + timedelta(
            minutes=stop.progress_minutes + stop.detour_minutes + dwell_so_far + detours_so_far
        )
        depart = arrive + timedelta(minutes=stop.dwell_minutes)
        if arrive > cursor:
            acts.append(_drive_activity(
                f"Drive — toward {stop.place.name}", day, cursor, arrive, route.sources, idx
            ))
        adjusted = StopPlan(stop.place, stop.category, arrive, depart, stop.detour_minutes,
                            stop.dwell_minutes, stop.progress_minutes, stop.reason)
        acts.append(_stop_activity(adjusted, day, idx))
        dwell_so_far += stop.dwell_minutes
        detours_so_far += stop.detour_minutes
        cursor = depart
        idx += 1

    arrival = departure + timedelta(
        minutes=route.total_duration_min + dwell_so_far
        + sum(s.detour_minutes for s in stops)
    )
    if cursor < arrival:
        acts.append(_drive_activity(drive_name, day, cursor, arrival, route.sources, idx))
    return acts, arrival


def _order_attractions(start: PlaceCandidate, pool: list[PlaceCandidate]) -> list[PlaceCandidate]:
    """Nearest-neighbour ordering from the accommodation/starting point."""
    remaining = list(pool)
    ordered: list[PlaceCandidate] = []
    current = start
    while remaining:
        remaining.sort(
            key=lambda c: (
                haversine_km(
                    (current.location.lat, current.location.lng),
                    (c.location.lat, c.location.lng),
                ) if current.location and c.location else 999
            )
        )
        nxt = remaining.pop(0)
        ordered.append(nxt)
        current = nxt
    return ordered


def _attraction_activity(
    req: TripRequest,
    place: PlaceCandidate,
    day: date,
    start: datetime,
    travel_min: int,
    idx: int,
    prior: PlaceCandidate,
) -> Activity:
    visit = place.estimated_visit_minutes or 60
    arrive = start
    depart = arrive + timedelta(minutes=visit)
    return Activity(
        id=_id(place.name, day, idx),
        type=ActivityType.attraction,
        name=place.name,
        day=day,
        planned_start=arrive.timetz().replace(tzinfo=None),
        planned_end=depart.timetz().replace(tzinfo=None),
        place=place,
        status=ActivityStatus.planned,
        sources=place.sources + [_calculated_source(
            f"{travel_min} min hop from {prior.name} estimated from straight-line distance; "
            "opening hours shown only when published."
        )],
        explanation=(
            f"Selected for your interests/must-visit list; ~{visit} min visit, "
            f"{travel_min} min from the previous stop."
        ),
    )


def build_days(
    req: TripRequest,
    route_out: RouteOption,
    route_back: RouteOption,
    stops_out: list[StopPlan],
    stops_back: list[StopPlan],
    attractions: list[PlaceCandidate],
    destination_food: list[PlaceCandidate],
    drop_count: int = 0,
) -> tuple[list[DayPlan], list[ExcludedActivity], PlaceCandidate | None]:
    """Build the day-by-day timeline. Returns (days, excluded, destination_anchor)."""
    days: list[DayPlan] = []
    excluded: list[ExcludedActivity] = []

    start = req.start_date
    ret = req.return_date or start
    departure_dt = at(start, req.departure_time)

    # --- Day 1: outbound drive.
    day1_acts, arrival = _travel_day(
        req, start, departure_dt, route_out, stops_out,
        f"Drive — {route_out.legs[-1].to_name}",
    )
    checkin = Activity(
        id=_id("checkin", start, 0),
        type=ActivityType.accommodation,
        name=f"Check-in — {req.destinations[-1]}",
        day=start,
        planned_start=arrival.timetz().replace(tzinfo=None),
        planned_end=(arrival + timedelta(minutes=CHECKIN_MINUTES)).timetz().replace(tzinfo=None),
        status=ActivityStatus.planned,
        explanation="Accommodation area held; hotel comparison lands in Phase 2.",
        sources=[_calculated_source("Check-in placeholder; no reservation made.")],
    )
    day1_acts.append(checkin)

    # --- Destination anchor for attraction ordering.
    anchor_place = attractions[0] if attractions else None
    if anchor_place is None and route_out.legs and route_out.legs[-1].to_point:
        anchor_place = PlaceCandidate(
            id="anchor",
            name=req.destinations[-1],
            category=PlaceCategory.accommodation,
            location=route_out.legs[-1].to_point,
        )

    # --- Attraction pool: must-visit first, then rating.
    must = [a for a in attractions if any(m.lower() in a.name.lower() for m in req.must_visit)]
    rest_pool = [a for a in attractions if a not in must]
    rest_pool.sort(key=lambda a: (-(a.rating or 0), a.name))
    ordered = must + (_order_attractions(anchor_place, rest_pool) if anchor_place else rest_pool)

    if drop_count:
        dropped_pool = [p for p in ordered if p not in must][-drop_count:]
        ordered = [p for p in ordered if p not in dropped_pool]
        for dropped in dropped_pool:
            excluded.append(ExcludedActivity(
                name=dropped.name,
                reason="Removed during feasibility repair: the remaining plan could not fit.",
                alternatives=["Extend the trip", "Leave earlier", "Drop another stop"],
            ))

    capacity = PACE_DAILY_VISIT_MINUTES[req.pace]
    day_windows: list[tuple[date, int, int]] = []
    cursor_day = start
    while cursor_day <= ret:
        if cursor_day == start:
            window_start = max(MORNING_START, minutes_of(checkin.planned_end) + 15)
            day_windows.append((cursor_day, window_start, EVENING_CUTOFF))
        elif cursor_day == ret:
            # Leave time for the return leg is computed below (backward from deadline).
            day_windows.append((cursor_day, MORNING_START, EVENING_CUTOFF))
        else:
            day_windows.append((cursor_day, MORNING_START, EVENING_CUTOFF))
        cursor_day += timedelta(days=1)

    scheduled_pool = list(ordered)
    day_plans: list[DayPlan] = []
    idx = 0

    for w_i, (day, win_start_min, win_end_min) in enumerate(day_windows):
        acts: list[Activity] = []
        if day == start:
            acts.extend(day1_acts)

        is_last = day == ret and req.return_date is not None
        leave_min = None
        if is_last:
            ret_duration = route_back.total_duration_min + sum(
                s.dwell_minutes + s.detour_minutes for s in stops_back
            )
            latest = (minutes_of(req.road.night_cutoff) - ret_duration - 15
                      if req.road.avoid_night_riding else 23 * 60 - ret_duration)
            if req.return_deadline:
                latest = min(latest, minutes_of(req.return_deadline) - ret_duration - 20)
            # Prefer a mid-afternoon return for short trips unless the deadline forces earlier.
            preferred = 15 * 60 if (ret - start).days <= 1 else 16 * 60
            leave_min = max(MORNING_START, min(preferred, latest))
            win_end_min = leave_min - 30  # buffer before departure

        used = 0
        current_place = anchor_place
        while scheduled_pool and used < capacity and (win_end_min - win_start_min) >= 60:
            cand = scheduled_pool[0]
            travel = intra_city_minutes(current_place, cand) if current_place else 15
            visit = cand.estimated_visit_minutes or 60
            slot_start = win_start_min + used + travel
            # Never arrive before published opening hours.
            if cand.opening_hours and cand.opening_hours.weekday_open:
                slot_start = max(slot_start, minutes_of(cand.opening_hours.weekday_open))
            close_min = (minutes_of(cand.opening_hours.weekday_close)
                         if cand.opening_hours and cand.opening_hours.weekday_close else win_end_min)
            if slot_start + visit > min(win_end_min, close_min) or used + travel + visit > capacity:
                break
            scheduled_pool.pop(0)
            start_dt = at(day, time_of(slot_start))
            acts.append(_attraction_activity(req, cand, day, start_dt, travel, idx, current_place or cand))
            used = (slot_start - win_start_min) + visit
            current_place = cand
            idx += 1

            # Lunch near 13:00 when a restaurant candidate is available.
            if destination_food and 12 * 60 <= minutes_of(acts[-1].planned_end) < 13 * 60 and slot_start + visit + 45 < win_end_min:
                lunch_place = destination_food[0]
                lunch_start = at(day, acts[-1].planned_end)
                acts.append(Activity(
                    id=_id(lunch_place.name, day, idx),
                    type=ActivityType.meal,
                    name=lunch_place.name,
                    day=day,
                    planned_start=acts[-1].planned_end,
                    planned_end=(lunch_start + timedelta(minutes=45)).timetz().replace(tzinfo=None),
                    place=lunch_place,
                    explanation="Lunch placed around 13:00 with a vegetarian option.",
                    sources=lunch_place.sources,
                ))
                used += 45
                idx += 1

        # Not enough room for even one attraction today.
        if day != start and not acts and scheduled_pool:
            pass  # handled by the return-leg below; exclusion decided by caller

        if is_last:
            leave_dt = at(day, time_of(leave_min))
            return_acts, _ = _travel_day(
                req, day, leave_dt, route_back, stops_back,
                f"Drive — {route_back.legs[-1].to_name}",
            )
            acts.extend(return_acts)

        acts.sort(key=lambda a: minutes_of(a.planned_start))
        day_plans.append(DayPlan(day=day, activities=acts))

    # Anything left unscheduled becomes an explicit exclusion.
    for cand in scheduled_pool:
        excluded.append(ExcludedActivity(
            name=cand.name,
            reason=(
                "Does not fit within the available time before the return departure "
                "at the chosen pace."
            ),
            alternatives=["Extend the trip", "Leave earlier", "Remove another attraction"],
        ))

    return day_plans, excluded, anchor_place


def build_budget(req: TripRequest, route_out: RouteOption, route_back: RouteOption) -> BudgetSummary:
    lines: list[BudgetLine] = []
    people = max(1, req.group.total)

    total_km = route_out.total_distance_km + (route_back.total_distance_km if req.includes_return else 0)
    for vehicle in req.vehicles:
        if not vehicle.mileage_km_per_litre:
            continue
        litres = total_km / vehicle.mileage_km_per_litre * vehicle.count
        amount = round(litres * FUEL_PRICE_INR_PER_L)
        lines.append(BudgetLine(
            category="fuel",
            amount_inr=amount,
            basis=f"{vehicle.count} vehicles × {round(total_km)} km ÷ {vehicle.mileage_km_per_litre} km/L × "
                  f"₹{FUEL_PRICE_INR_PER_L}/L (assumed price — verify locally)",
            per_person_inr=round(amount / people),
        ))

    days = max(1, (req.return_date - req.start_date).days + 1) if req.return_date else 1
    food_total = FOOD_INR_PER_PERSON_DAY * people * days
    lines.append(BudgetLine(
        category="food",
        amount_inr=food_total,
        basis=f"₹{FOOD_INR_PER_PERSON_DAY}/person/day × {people} people × {days} days (planning estimate)",
        per_person_inr=FOOD_INR_PER_PERSON_DAY * days,
    ))

    total = sum(l.amount_inr for l in lines)
    budget_total = req.budget.total_inr or (req.budget.per_person_inr * people if req.budget.per_person_inr else None)

    return BudgetSummary(
        lines=lines,
        total_inr=total,
        per_person_inr=round(total / people),
        within_budget=(total <= budget_total) if budget_total else None,
    )
