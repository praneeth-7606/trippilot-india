"""Output-side domain models: routes, places, and the scheduled itinerary."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
import re
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceKind(str, Enum):
    retrieved = "retrieved"      # came from a provider response
    calculated = "calculated"    # computed by our scheduler
    unknown = "unknown"          # provider did not return this field


class SourceEvidence(BaseModel):
    kind: EvidenceKind
    engine: Optional[str] = None      # e.g. google_maps_directions
    url: Optional[str] = None         # provider or official source link
    title: Optional[str] = None
    retrieved_at: datetime
    note: Optional[str] = None


class GeoPoint(BaseModel):
    lat: float
    lng: float


class PlaceCategory(str, Enum):
    attraction = "attraction"
    restaurant = "restaurant"
    fuel = "fuel"
    washroom = "washroom"
    rest = "rest"
    accommodation = "accommodation"
    waypoint = "waypoint"


class OpeningHours(BaseModel):
    """Published hours when a provider returned them; otherwise all None."""
    weekday_open: Optional[time] = None
    weekday_close: Optional[time] = None
    sunday_open: Optional[time] = None
    sunday_close: Optional[time] = None
    raw: Optional[str] = None
    source: Optional[SourceEvidence] = None
    weekly: dict[str, str] = Field(default_factory=dict)

    def for_day(self, day: date):
        """Return (opens, closes, explicitly_closed) for the requested weekday.

        Split sessions or ambiguous formats remain unknown rather than inventing
        an uninterrupted interval. Today's 'open now' badge is not a schedule.
        """
        if self.weekly:
            raw = self.weekly.get(day.strftime("%A").lower(), "")
            if raw.strip().lower() == "closed":
                return None, None, True
            if "24 hours" in raw.lower():
                return time(0), time(23, 59), False
            clocks = re.findall(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", raw, re.I)
            if len(clocks) != 2:
                return None, None, False
            values = []
            for hour, minute, ampm in clocks:
                h = int(hour) % 12 + (12 if ampm.upper() == "PM" else 0)
                values.append(time(h, int(minute or 0)))
            return values[0], values[1], False
        if day.weekday() == 6 and (self.sunday_open or self.sunday_close):
            return self.sunday_open, self.sunday_close, False
        return self.weekday_open, self.weekday_close, False


class PlaceCandidate(BaseModel):
    id: str
    name: str
    category: PlaceCategory
    address: Optional[str] = None
    location: Optional[GeoPoint] = None
    opening_hours: Optional[OpeningHours] = None
    rating: Optional[float] = None
    price_level: Optional[int] = None
    estimated_visit_minutes: Optional[int] = None
    detour_minutes: Optional[int] = None   # extra time off the selected route
    notes: Optional[str] = None
    sources: list[SourceEvidence] = Field(default_factory=list)


class TravelMode(str, Enum):
    driving = "driving"
    two_wheeler = "two_wheeler"


class RouteStep(BaseModel):
    """A turn-by-turn step; coordinates let us place stops along the route."""
    title: str
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    gps_coordinates: Optional[GeoPoint] = None


class RouteLeg(BaseModel):
    id: str
    from_name: str
    to_name: str
    from_point: Optional[GeoPoint] = None
    to_point: Optional[GeoPoint] = None
    distance_km: float
    duration_min: int
    travel_mode: TravelMode
    summary: Optional[str] = None
    navigation_url: Optional[str] = None
    steps: list[RouteStep] = Field(default_factory=list)
    sources: list[SourceEvidence] = Field(default_factory=list)


class RouteOption(BaseModel):
    id: str
    label: str                        # e.g. "Fastest", "Via NH-183"
    legs: list[RouteLeg]
    total_distance_km: float
    total_duration_min: int
    warnings: list[str] = Field(default_factory=list)
    sources: list[SourceEvidence] = Field(default_factory=list)


class ActivityType(str, Enum):
    drive = "drive"
    meal = "meal"
    fuel = "fuel"
    washroom = "washroom"
    rest = "rest"
    attraction = "attraction"
    accommodation = "accommodation"
    free = "free"


class ActivityStatus(str, Enum):
    planned = "planned"
    locked = "locked"
    skipped = "skipped"
    completed = "completed"


class Activity(BaseModel):
    id: str
    type: ActivityType
    name: str
    day: date
    planned_start: time
    planned_end: time
    place: Optional[PlaceCandidate] = None
    leg_in: Optional[RouteLeg] = None          # travel leg that precedes this activity
    cost_inr: Optional[int] = None
    cost_basis: Optional[str] = None
    status: ActivityStatus = ActivityStatus.planned
    explanation: Optional[str] = None
    sources: list[SourceEvidence] = Field(default_factory=list)
    activity_group: Optional[str] = None       # links legs/stops of one segment


class ExcludedActivity(BaseModel):
    name: str
    reason: str
    alternatives: list[str] = Field(default_factory=list)


class FeasibilitySeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class FeasibilityIssue(BaseModel):
    code: str
    severity: FeasibilitySeverity
    message: str
    related_activity_ids: list[str] = Field(default_factory=list)


class DayPlan(BaseModel):
    day: date
    activities: list[Activity]


class BudgetLine(BaseModel):
    category: str
    amount_inr: int
    basis: str
    per_person_inr: Optional[int] = None
    sources: list[SourceEvidence] = Field(default_factory=list)


class BudgetSummary(BaseModel):
    lines: list[BudgetLine]
    total_inr: int
    per_person_inr: Optional[int] = None
    within_budget: Optional[bool] = None


class WeatherDay(BaseModel):
    day: date
    summary: Optional[str] = None
    max_c: Optional[float] = None
    min_c: Optional[float] = None
    precipitation_probability: Optional[int] = None
    sources: list[SourceEvidence] = Field(default_factory=list)


class Advisory(BaseModel):
    text: str
    url: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class PlanStatus(str, Enum):
    planning = "planning"
    ready = "ready"
    partial = "partial"
    failed = "failed"


class ItineraryVersion(BaseModel):
    timezone: str = "Asia/Kolkata"
    version: int
    created_at: datetime
    status: PlanStatus
    days: list[DayPlan]
    route: Optional[RouteOption] = None
    route_alternatives: list[RouteOption] = Field(default_factory=list)
    excluded: list[ExcludedActivity] = Field(default_factory=list)
    issues: list[FeasibilityIssue] = Field(default_factory=list)
    budget: Optional[BudgetSummary] = None
    weather: list[WeatherDay] = Field(default_factory=list)
    advisories: list[Advisory] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
