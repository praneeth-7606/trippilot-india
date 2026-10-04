"""Route-aware stop selection: meals, fuel, washrooms, rest along the actual route.

Candidates are matched to the nearest route step, so a stop must be practical
*along* the journey — detour time is calculated before a stop is chosen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from app.models.itinerary import PlaceCandidate, PlaceCategory, RouteOption
from app.models.trip import FoodPreferences, RoadPreferences, VehicleProfile
from app.planner.timeutil import add_minutes, haversine_km, minutes_of


@dataclass
class StopPlan:
    place: PlaceCandidate
    category: PlaceCategory
    arrive_at: datetime          # time reaching the stop vicinity (before detour)
    depart_at: datetime          # time leaving the stop (after detour + dwell)
    detour_minutes: int
    dwell_minutes: int
    progress_minutes: int        # driving minutes from departure to stop along route
    reason: str


def _coord(step: dict) -> Optional[tuple[float, float]]:
    c = step.get("gps_coordinates")
    if not c:
        return None
    if "latitude" in c and "longitude" in c:
        return (c["latitude"], c["longitude"])
    if "lat" in c and "lng" in c:
        return (c["lat"], c["lng"])
    return None


def nearest_step_index(location: tuple[float, float], steps: list[dict]) -> tuple[int, float]:
    """Index of the closest route step coordinate and the detour km (round trip)."""
    best_i, best_d = 0, float("inf")
    for i, step in enumerate(steps):
        c = _coord(step)
        if not c:
            continue
        d = haversine_km(location, c)
        if d < best_d:
            best_i, best_d = i, d
    return best_i, best_d * 2  # leave and rejoin the route


def stop_progress(
    candidate: PlaceCandidate,
    leg_steps: list[dict],
    leg_duration_min: int,
) -> tuple[int, int]:
    """(progress minutes along leg, detour minutes). Needs route step geometry."""
    if not candidate.location or not leg_steps:
        return leg_duration_min // 2, 15  # conservative default when no geometry
    idx, detour_km = nearest_step_index((candidate.location.lat, candidate.location.lng), leg_steps)
    distances = route_distances(leg_steps)
    progress = round(leg_duration_min * distances[idx] / distances[-1]) if distances[-1] else 0
    if detour_km == float("inf"):
        return leg_duration_min // 2, 999
    # Off-route surface streets ≈ 30 km/h effective for the round-trip detour.
    detour = max(2, round(detour_km / 30 * 60))
    return progress, detour


def route_distances(steps):
    """Cumulative geometry distance; turn density is not elapsed travel time."""
    distances, total, previous = [], 0.0, None
    for step in steps:
        current = _coord(step)
        if current and previous:
            total += haversine_km(previous, current)
        if current:
            previous = current
        distances.append(total)
    return distances or [0.0]


def route_midpoint(route):
    steps = [s.model_dump() for s in route.legs[0].steps]
    distances = route_distances(steps)
    for i, distance in enumerate(distances):
        if distance >= distances[-1] / 2 and i < len(route.legs[0].steps):
            return route.legs[0].steps[i].gps_coordinates
    return route.legs[0].from_point


def pick_best(
    candidates: list[PlaceCandidate],
    category: PlaceCategory,
    target_minutes: int,
    leg_steps: list[dict],
    leg_duration_min: int,
    taken_ids: set[str],
    preferences: Optional[FoodPreferences] = None,
) -> Optional[PlaceCandidate]:
    """Choose the candidate whose stop fits best around target_minutes."""
    scored: list[tuple[int, PlaceCandidate, int, int]] = []
    for c in candidates:
        if c.id in taken_ids or c.category != category:
            continue
        progress, detour = stop_progress(c, leg_steps, leg_duration_min)
        if detour > 20 or abs(progress - target_minutes) > 60:
            continue  # a large detour is not "on the way"
        score = abs(progress - target_minutes) + detour * 2
        if category == PlaceCategory.restaurant and preferences and preferences.vegetarian:
            name = c.name.lower()
            if any(w in name for w in ("veg", "vegetarian", "pure veg")):
                score -= 20
            elif any(w in name for w in ("non-veg", "chicken", "mutton", "biryani")):
                score += 40
        scored.append((score, c, progress, detour))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0])
    _, chosen, _, _ = scored[0]
    return chosen


def plan_stops(
    route: RouteOption,
    departure: datetime,
    food: FoodPreferences,
    road: RoadPreferences,
    vehicles: list[VehicleProfile],
    meals: list[PlaceCandidate],
    fuel_stations: list[PlaceCandidate],
    washrooms: list[PlaceCandidate],
    rests: list[PlaceCandidate],
) -> list[StopPlan]:
    """Walk the route clock and place practical stops. Deterministic."""
    stops: list[StopPlan] = []
    taken: set[str] = set()

    total_km = route.total_distance_km
    total_min = route.total_duration_min
    leg_steps: list[dict] = []
    if route.legs:
        leg_steps = [s.model_dump() for s in route.legs[0].steps]

    # --- Meals: target 13:00 lunch unless the route cannot reach it in time.
    minutes_from_departure = minutes_of(time(13, 0)) - minutes_of(departure.timetz().replace(tzinfo=None))
    lunch_target = minutes_from_departure if 30 <= minutes_from_departure <= total_min - 20 else total_min // 2
    lunch = pick_best(meals, PlaceCategory.restaurant, lunch_target, leg_steps, total_min, taken, food)
    if lunch and total_min >= 90:
        progress, detour = stop_progress(lunch, leg_steps, total_min)
        arrive = add_minutes(departure, progress)
        dwell = 40
        stops.append(StopPlan(
            place=lunch, category=PlaceCategory.restaurant,
            arrive_at=add_minutes(arrive, detour), depart_at=add_minutes(arrive, detour + dwell),
            detour_minutes=detour, dwell_minutes=dwell, progress_minutes=progress,
            reason=f"Chosen because it is on the route around {arrive.strftime('%H:%M')}, "
                   f"adds ~{detour} min detour, and matches your food preference.",
        ))
        taken.add(lunch.id)

    # --- Washroom attached near the meal stop when possible, else mid-route.
    wash_target = stops[0].progress_minutes if stops else total_min // 2
    wash = pick_best(washrooms, PlaceCategory.washroom, wash_target, leg_steps, total_min, taken)
    if wash:
        progress, detour = stop_progress(wash, leg_steps, total_min)
        arrive = add_minutes(departure, progress)
        dwell = 10
        stops.append(StopPlan(
            place=wash, category=PlaceCategory.washroom,
            arrive_at=add_minutes(arrive, detour), depart_at=add_minutes(arrive, detour + dwell),
            detour_minutes=detour, dwell_minutes=dwell, progress_minutes=progress,
            reason="Published as a public facility close to the planned meal stop.",
        ))
        taken.add(wash.id)

    # --- Fuel only when vehicle range data supports the calculation.
    ranges = [v.effective_range_km for v in vehicles if v.effective_range_km]
    range_km = min(ranges) if ranges else None
    if range_km and fuel_stations:
        threshold = range_km * 0.8
        if total_km > threshold:
            fuel_target = int(total_min * (threshold / max(total_km, 0.1)))
            fuel = pick_best(fuel_stations, PlaceCategory.fuel, fuel_target, leg_steps, total_min, taken)
            if fuel:
                progress, detour = stop_progress(fuel, leg_steps, total_min)
                arrive = add_minutes(departure, progress)
                dwell = 12
                stops.append(StopPlan(
                    place=fuel, category=PlaceCategory.fuel,
                    arrive_at=add_minutes(arrive, detour), depart_at=add_minutes(arrive, detour + dwell),
                    detour_minutes=detour, dwell_minutes=dwell, progress_minutes=progress,
                    reason=f"Fuel stop scheduled before the reserve threshold "
                           f"(effective range ~{round(range_km)} km vs {round(total_km)} km journey).",
                ))
                taken.add(fuel.id)

    # --- Rest break every break_every_minutes of continuous travel.
    last_break = 0
    for target in range(road.break_every_minutes, total_min - 20, road.break_every_minutes):
        # A meal, fuel or washroom stop already supplies a break in this window.
        if any(abs(s.progress_minutes - target) <= 35 for s in stops):
            continue
        rest = pick_best(rests, PlaceCategory.rest, target, leg_steps, total_min, taken)
        if not rest:
            break
        progress, detour = stop_progress(rest, leg_steps, total_min)
        if progress <= last_break + 30 or abs(progress - target) > 45:
            continue
        arrive = add_minutes(departure, progress)
        dwell = 15
        stops.append(StopPlan(
            place=rest, category=PlaceCategory.rest,
            arrive_at=add_minutes(arrive, detour), depart_at=add_minutes(arrive, detour + dwell),
            detour_minutes=detour, dwell_minutes=dwell, progress_minutes=progress,
            reason=f"Rest placed after ~{road.break_every_minutes} min of continuous travel.",
        ))
        taken.add(rest.id)
        last_break = progress

    stops.sort(key=lambda s: s.progress_minutes)
    return stops
