"""Trip endpoints: create, plan, inspect, patch activities, replan, share."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.itinerary import ActivityStatus, ItineraryVersion, PlanStatus
from app.models.trip import TripRequest
from app.planner.pipeline import PlanningPipeline
from app.planner.replan import apply_delay
from app.planner.feasibility import check
from app.services.store import get_store

router = APIRouter(prefix="/trips", tags=["trips"])


class PlanResponse(BaseModel):
    trip_id: str
    version: ItineraryVersion
    search_budget_used: int


class ActivityPatch(BaseModel):
    status: ActivityStatus


class ReplanRequest(BaseModel):
    delay_minutes: int = Field(ge=0, le=24 * 60)
    from_activity_id: Optional[str] = None


class ShareResponse(BaseModel):
    share_url: str


@router.post("", status_code=201)
def create_trip(request: TripRequest):
    trip = get_store().create(request)
    return {"id": trip.id, "created_at": trip.created_at, "status": trip.status}


@router.post("/{trip_id}/plan", response_model=PlanResponse)
def plan_trip(trip_id: str):
    store = get_store()
    trip = store.get(trip_id)
    if not trip:
        raise HTTPException(404, "trip not found")

    trip.emit("plan_started", "Parsing request and validating constraints.")
    pipeline = PlanningPipeline()
    trip.emit("route", "Retrieving route candidates.")
    version = pipeline.plan(trip.request, version=len(trip.versions) + 1)
    trip.emit("schedule", "Building the day-by-day timeline with route-aware stops.")
    trip.emit("validated", f"Feasibility checks complete: {len(version.issues)} issue(s).")

    store.add_version(trip_id, version)
    return PlanResponse(
        trip_id=trip_id, version=version, search_budget_used=pipeline.budget.used
    )


@router.get("/{trip_id}")
def get_trip(trip_id: str):
    trip = get_store().get(trip_id)
    if not trip:
        raise HTTPException(404, "trip not found")
    return {
        "id": trip.id,
        "status": trip.status,
        "request": trip.request.model_dump(mode="json"),
        "current_version": trip.current.version if trip.current else None,
        "versions": [v.version for v in trip.versions],
        "current": trip.current,
        "share_token": trip.share_token,
    }


@router.get("/{trip_id}/events")
def trip_events(trip_id: str):
    """Server-sent events: replays planning progress, then closes."""
    trip = get_store().get(trip_id)
    if not trip:
        raise HTTPException(404, "trip not found")

    def stream():
        for event in trip.events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.patch("/{trip_id}/activities/{activity_id}")
def patch_activity(trip_id: str, activity_id: str, patch: ActivityPatch):
    store = get_store()
    trip = store.get(trip_id)
    if not trip:
        raise HTTPException(404, "trip not found")
    version = trip.current
    if not version:
        raise HTTPException(409, "no plan yet")
    version = version.model_copy(deep=True)
    version.version += 1
    for day in version.days:
        for act in day.activities:
            if act.id == activity_id:
                act.status = patch.status
                version.created_at = datetime.now(timezone.utc)
                version.issues = check(trip.request, version)
                version.status = PlanStatus.partial if any(i.severity == "error" for i in version.issues) else PlanStatus.ready
                store.add_version(trip_id, version)
                trip.emit("activity_updated", f"{act.name} → {patch.status.value}")
                return {"ok": True, "activity": act.model_dump(mode="json"), "version": version}
    raise HTTPException(404, "activity not found")


@router.post("/{trip_id}/replan", response_model=PlanResponse)
def replan(trip_id: str, body: ReplanRequest):
    store = get_store()
    trip = store.get(trip_id)
    if not trip:
        raise HTTPException(404, "trip not found")
    version = trip.current
    if not version:
        raise HTTPException(409, "no plan yet")

    if body.from_activity_id and not any(a.id == body.from_activity_id for d in version.days for a in d.activities):
        raise HTTPException(404, "anchor activity not found")
    trip.emit("replan", f"Replanning after a {body.delay_minutes}-minute delay.")
    new_version = apply_delay(
        trip.request, version, body.delay_minutes, body.from_activity_id
    )
    store.add_version(trip_id, new_version)
    return PlanResponse(trip_id=trip_id, version=new_version, search_budget_used=0)


@router.post("/{trip_id}/share", response_model=ShareResponse)
def share_trip(trip_id: str):
    store = get_store()
    trip = store.get(trip_id)
    if not trip:
        raise HTTPException(404, "trip not found")
    if not trip.share_token:
        trip.share_token = uuid.uuid4().hex
    return ShareResponse(share_url=f"/trips/shared/{trip.share_token}")


@router.get("/shared/{share_token}", include_in_schema=False)
def shared_trip(share_token: str):
    for trip in get_store()._trips.values():
        if trip.share_token == share_token:
            return {
                "read_only": True,
                "request": trip.request.model_dump(mode="json"),
                "current": trip.current.model_dump(mode="json") if trip.current else None,
            }
    raise HTTPException(404, "shared trip not found")
