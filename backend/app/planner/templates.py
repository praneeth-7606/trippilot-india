"""Curated itinerary templates (Part C): small editable catalog, prefilled."""

from __future__ import annotations

from typing import Any

TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "coimbatore-munnar-bikes",
        "title": "Coimbatore → Munnar motorcycle weekend",
        "tagline": "Two days out and back, group of friends, no riding after dark.",
        "duration_days": 2,
        "interests": ["hill station", "scenic drive", "tea gardens"],
        "indicative_budget_inr_per_person": 5000,
        "route_variants": ["NH-183 via Udumalpet"],
        "prefill": {
            "origin": "Coimbatore",
            "destinations": ["Munnar"],
            "departure_time": "06:00",
            "transport_mode": "motorcycle",
            "pace": "balanced",
            "road": {
                "avoid_night_riding": True,
                "night_cutoff": "18:30",
                "max_daily_drive_minutes": 420,
            },
            "food": {"vegetarian": True},
            "group": {"adults": 6, "group_type": "friends"},
            "vehicles": [
                {"mode": "motorcycle", "count": 3, "mileage_km_per_litre": 40, "tank_litres": 12}
            ],
            "budget": {"per_person_inr": 5000},
            "must_visit": ["Tea Museum", "Mattupetty Dam"],
        },
    },
    {
        "id": "ooty-hill-weekend",
        "title": "Coimbatore → Ooty hill-station weekend",
        "tagline": "Family car trip via Mettupalayam, botanical gardens and lake.",
        "duration_days": 2,
        "interests": ["hill station", "gardens", "family"],
        "indicative_budget_inr_per_person": 4500,
        "route_variants": ["Mettupalayam ghat road"],
        "prefill": {
            "origin": "Coimbatore",
            "destinations": ["Ooty"],
            "departure_time": "07:00",
            "transport_mode": "car",
            "pace": "relaxed",
            "group": {"adults": 4, "children": 2, "group_type": "family"},
            "budget": {"per_person_inr": 4500},
        },
    },
    {
        "id": "madurai-heritage",
        "title": "Chennai → Madurai heritage circuit",
        "tagline": "Temple city deep dive with an overnight stay.",
        "duration_days": 2,
        "interests": ["heritage", "temples", "food"],
        "indicative_budget_inr_per_person": 6000,
        "route_variants": ["NH-44 expressway"],
        "prefill": {
            "origin": "Chennai",
            "destinations": ["Madurai"],
            "departure_time": "06:30",
            "transport_mode": "car",
            "pace": "balanced",
            "group": {"adults": 2, "group_type": "mixed"},
            "must_visit": ["Meenakshi Amman Temple"],
        },
    },
    {
        "id": "pondicherry-coast",
        "title": "Chennai → Pondicherry coastal drive",
        "tagline": "East Coast Road, beach time, and café stops.",
        "duration_days": 2,
        "interests": ["coast", "cafes", "relaxed"],
        "indicative_budget_inr_per_person": 4000,
        "route_variants": ["ECR / NH-32"],
        "prefill": {
            "origin": "Chennai",
            "destinations": ["Pondicherry"],
            "departure_time": "08:00",
            "transport_mode": "car",
            "pace": "relaxed",
            "group": {"adults": 4, "group_type": "friends"},
        },
    },
]


def list_templates() -> list[dict[str, Any]]:
    return TEMPLATES
