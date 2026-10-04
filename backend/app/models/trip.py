"""Input-side domain models: what the user gives TripPilot India."""

from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TransportMode(str, Enum):
    car = "car"
    motorcycle = "motorcycle"
    flight = "flight"
    train = "train"


class TravelPace(str, Enum):
    relaxed = "relaxed"
    balanced = "balanced"
    packed = "packed"


class GroupType(str, Enum):
    family = "family"
    friends = "friends"
    solo = "solo"
    mixed = "mixed"


class TravellerGroup(BaseModel):
    adults: int = Field(ge=1, le=40)
    children: int = Field(default=0, ge=0, le=40)
    elderly: int = Field(default=0, ge=0, le=40)
    group_type: GroupType = GroupType.friends

    @property
    def total(self) -> int:
        return self.adults + self.children + self.elderly


class VehicleProfile(BaseModel):
    mode: TransportMode = TransportMode.car
    count: int = Field(default=1, ge=1, le=20)
    fuel_type: Optional[str] = None
    mileage_km_per_litre: Optional[float] = Field(default=None, gt=0)
    tank_litres: Optional[float] = Field(default=None, gt=0)
    usable_range_km: Optional[float] = Field(default=None, gt=0)
    reserve_fraction: float = Field(default=0.15, ge=0, lt=0.5)

    @property
    def effective_range_km(self) -> Optional[float]:
        """Range after reserve, when enough data is provided."""
        if self.usable_range_km:
            return self.usable_range_km * (1 - self.reserve_fraction)
        if self.mileage_km_per_litre and self.tank_litres:
            return self.mileage_km_per_litre * self.tank_litres * (1 - self.reserve_fraction)
        return None


class FoodPreferences(BaseModel):
    vegetarian: bool = False
    vegan: bool = False
    jain: bool = False
    allergies: list[str] = Field(default_factory=list)
    cuisine_notes: Optional[str] = None


class AccommodationRequirements(BaseModel):
    rooms: int = Field(default=1, ge=1, le=20)
    max_occupancy_per_room: int = Field(default=3, ge=1, le=6)
    budget_per_night_inr: Optional[int] = Field(default=None, gt=0)
    parking: bool = False
    breakfast: bool = False
    accessibility: bool = False


class Budget(BaseModel):
    total_inr: Optional[int] = Field(default=None, gt=0)
    per_person_inr: Optional[int] = Field(default=None, gt=0)
    accommodation_inr: Optional[int] = Field(default=None, ge=0)
    food_inr: Optional[int] = Field(default=None, ge=0)
    fuel_inr: Optional[int] = Field(default=None, ge=0)
    activities_inr: Optional[int] = Field(default=None, ge=0)

    @property
    def effective_total_inr(self) -> Optional[int]:
        if self.total_inr:
            return self.total_inr
        if self.per_person_inr:
            return self.per_person_inr
        return None


class RoadPreferences(BaseModel):
    max_daily_drive_minutes: int = Field(default=360, ge=30, le=900)
    break_every_minutes: int = Field(default=120, ge=30, le=240)
    meal_times: list[time] = Field(default_factory=lambda: [time(13, 0), time(20, 0)])
    avoid_tolls: bool = False
    avoid_night_riding: bool = False
    night_cutoff: time = time(18, 30)


class TripRequest(BaseModel):
    origin: str
    destinations: list[str] = Field(min_length=1)
    start_date: date
    return_date: Optional[date] = None
    departure_time: time = time(6, 0)
    return_deadline: Optional[time] = None
    timezone: str = "Asia/Kolkata"
    transport_mode: TransportMode = TransportMode.car
    group: TravellerGroup
    vehicles: list[VehicleProfile] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    food: FoodPreferences = Field(default_factory=FoodPreferences)
    accommodation: AccommodationRequirements = Field(default_factory=AccommodationRequirements)
    road: RoadPreferences = Field(default_factory=RoadPreferences)
    must_visit: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    pace: TravelPace = TravelPace.balanced
    natural_language: Optional[str] = None
    currency: str = "INR"

    @field_validator("timezone")
    @classmethod
    def supported_timezone(cls, value):
        if value != "Asia/Kolkata":
            raise ValueError("Phase 1 supports Asia/Kolkata only")
        return value

    @field_validator("transport_mode")
    @classmethod
    def road_transport_only(cls, value):
        if value not in (TransportMode.car, TransportMode.motorcycle):
            raise ValueError("Phase 1 supports cars and motorcycles only")
        return value

    @field_validator("destinations")
    @classmethod
    def one_destination(cls, value):
        if len(value) != 1:
            raise ValueError("Phase 1 supports one destination plus the return journey")
        return value

    @field_validator("return_date")
    @classmethod
    def return_after_start(cls, v: Optional[date], info):
        if v and info.data.get("start_date") and v < info.data["start_date"]:
            raise ValueError("return_date cannot be before start_date")
        if v and (v - info.data["start_date"]).days > 15:
            raise ValueError("Trips are limited to 16 days in Phase 1")
        return v

    @property
    def trip_days(self) -> int:
        if self.return_date and self.return_date != self.start_date:
            return (self.return_date - self.start_date).days + 1
        return 1

    @property
    def includes_return(self) -> bool:
        return self.return_date is not None


class TripRequestForm(TripRequest):
    """Alias kept for API clarity: the structured-form input path."""
