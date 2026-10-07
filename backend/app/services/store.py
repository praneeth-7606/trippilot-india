"""In-memory trip store (Phase 1). Postgres persistence lands in Phase 2."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.models.itinerary import ItineraryVersion, PlanStatus
from app.models.trip import TripRequest


@dataclass
class TripRecord:
    id: str
    request: TripRequest
    created_at: datetime
    versions: list[ItineraryVersion] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    share_token: Optional[str] = None
    status: PlanStatus = PlanStatus.planning

    def emit(self, kind: str, message: str) -> None:
        self.events.append({
            "type": kind,
            "message": message,
            "at": datetime.now(timezone.utc).isoformat(),
        })

    @property
    def current(self) -> Optional[ItineraryVersion]:
        return self.versions[-1] if self.versions else None


class TripStore:
    def __init__(self) -> None:
        self._trips: dict[str, TripRecord] = {}
        self._lock = threading.Lock()

    def create(self, request: TripRequest) -> TripRecord:
        trip = TripRecord(
            id=uuid.uuid4().hex,
            request=request,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._trips[trip.id] = trip
        return trip

    def get(self, trip_id: str) -> Optional[TripRecord]:
        return self._trips.get(trip_id)

    def add_version(self, trip_id: str, version: ItineraryVersion) -> Optional[TripRecord]:
        with self._lock:
            trip = self._trips.get(trip_id)
            if not trip:
                return None
            # Planning calls can complete out of order; the store owns final version allocation.
            version.version = max((item.version for item in trip.versions), default=0) + 1
            trip.versions.append(version)
            trip.versions.sort(key=lambda item: item.version)
            trip.status = version.status
            return trip


_store: Optional[TripStore] = None


def get_store() -> TripStore:
    global _store
    if _store is None:
        _store = TripStore()
    return _store
