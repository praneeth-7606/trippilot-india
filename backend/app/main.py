"""TripPilot India — FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import templates, trips
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="TripPilot India",
    description=(
        "AI travel agent for India: route-aware group trip planning with "
        "feasibility checks and explainable replanning. SerpApi India Hackathon 2026."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router)
app.include_router(templates.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "fixture_mode": settings.fixture_mode,
        "llm_enabled": settings.llm_enabled,
        "search_budget": settings.trippilot_search_budget,
    }
