# TripPilot India

**An AI travel agent that plans the journey, the stops, and the destination activities around a group's actual constraints.**

Built for the [SerpApi India Hackathon 2026](https://serpapi.com/blog/introducing-the-serpapi-india-hackathon-2026/) — Track: **Travel & Local Discovery**.

## What it does

TripPilot India builds realistic door-to-door group itineraries for Indian road trips: outbound travel, route-aware stops (meals, fuel, washrooms, rest), destination activities, accommodation, and the return leg — all checked against the group's real constraints.

The first version focuses on **cars and motorcycles**, with a concrete demo scenario: *six friends, three motorcycles, Coimbatore to Munnar, two days including the return journey.*

### Core differentiators

- **Route-aware stop planning** — stops are placed along the actual route at practical points, with detour time calculated, not just "nearby places."
- **Schedule feasibility checking** — detects excessive travel, missed opening hours, overlapping activities, and late returns before the user leaves.
- **Group logistics** — multiple vehicles, shared expenses, room preferences, food constraints, no-riding-after-dark rules.
- **Explainable, delay-aware replanning** — "We left 90 minutes late" recalculates the remaining schedule while preserving locked bookings, and every recommendation states why it was chosen.

## SerpApi usage

| Engine | Role |
| --- | --- |
| Google Maps | Attractions, restaurants, fuel stations, washrooms, accommodation locations |
| Google Maps Directions | Route candidates, distance, duration (driving + two-wheeler modes) |
| Google Hotels | Accommodation search by dates and group configuration |
| Google Search | Official attraction rules, permits, advisories, event information |
| Google Flights | Flight options (after the road-trip workflow ships) |

Plus Open-Meteo for weather forecasts where available.

Search results are presented as **options with sources and retrieval timestamps**, never as confirmed bookings.

## Stack

- **Frontend:** React + TypeScript + Tailwind
- **Backend:** FastAPI + Pydantic
- **Agent workflow:** LangGraph (one configurable LLM provider)
- **Data:** PostgreSQL (persistent), Redis (cache)
- **Scheduling:** deterministic Python logic for time, budget, opening hours, breaks, and constraint validation

## Status

Phase 1 in progress: road planning, route-aware stops, attractions, timeline, map, and sources.

## Repository conventions

- Public repository; commit history is reviewed by judges.
- AI assistance is used and disclosed below.
- All API keys stay on the backend, loaded from environment variables. No secrets are committed.

## License

MIT
