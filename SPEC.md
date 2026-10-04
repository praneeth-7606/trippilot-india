# TripPilot India — Product Specification

Version 1.0 — Hackathon MVP scope.

## Product goal

Create realistic door-to-door group itineraries, including outbound travel,
destination activities, accommodation, and return travel.
Prioritize cars and motorcycles for the hackathon MVP.

## Input

Accept a structured trip form and natural-language requests.

Capture origin, destinations, dates, departure time, return deadline,
transport mode, travellers, vehicles, budget, must-visit attractions,
food preferences, accommodation requirements, travel pace, maximum
daily driving/riding time, and optional vehicle fuel-range information.

- Ask targeted follow-up questions for important missing information.
- Distinguish hard constraints from preferences.
- All trip times must include an explicit timezone; use Asia/Kolkata
  for Indian trips.

## Workflow

1. Parse and validate the request.
2. Retrieve suitable route candidates.
3. Discover destination attractions and route-adjacent stop candidates.
4. Search accommodation for the relevant dates and group configuration.
5. Retrieve available weather and relevant official advisories.
6. Normalize provider results with coordinates, source links,
   retrieval timestamps, and missing-data indicators.
7. Construct an itinerary using deterministic scheduling logic.
8. Validate travel time, opening hours, breaks, accommodation,
   budget assumptions, and return deadline.
9. Revise infeasible plans within a bounded number of attempts.
10. Return an editable itinerary with explanations and alternatives.

## SerpApi integrations

- Google Maps for places and stop discovery.
- Google Maps Directions for driving and two-wheeler routing.
- Google Hotels for accommodation search.
- Google Search for official attraction information and advisories.
- Add Google Flights after the road-trip workflow works.
- Use Open-Meteo for available forecasts.

## Scheduling rules

- Include outbound and return travel.
- Calculate stop detours using route travel time.
- Schedule meals and rest based on user preferences.
- Schedule fuel stops only when range information supports the calculation.
- Respect published attraction hours where available.
- Preserve locked activities and confirmed reservations during replanning.
- If required constraints cannot be met, explain the conflict and ask
  the user to choose a trade-off.
- Never silently remove a must-visit attraction.

## Interface

- Homepage: curated Indian itinerary templates and Start Planning.
- Planner: input form plus conversational clarification.
- Results: synchronized map and day-by-day timeline.
- Separate panels: route alternatives, accommodation, budget,
  warnings, sources, and excluded attractions.
- Allow users to lock, remove, replace, or reorder activities.
- Provide a "We are delayed" action to replan remaining activities.
- Support shared read-only trip links and a printable summary.

## Data models

TripRequest, TravellerGroup, VehicleProfile, PlaceCandidate,
RouteLeg, AccommodationOffer, Activity, ItineraryVersion,
CostEstimate, Advisory, and SourceEvidence.

Each scheduled activity must store its location, estimated arrival,
departure, duration, preceding travel leg, cost assumptions,
source references, and confirmation status.

Suggested endpoints:

- `POST /trips`
- `POST /trips/{id}/plan`
- `GET /trips/{id}`
- `GET /trips/{id}/events`
- `POST /trips/{id}/replan`
- `PATCH /trips/{id}/activities/{activity_id}`
- `GET /itinerary-templates`
- `POST /trips/{id}/share`

## Reliability

- Validate structured LLM outputs with Pydantic.
- Use timeouts, bounded retries, caching, and per-trip search budgets.
- Do not invent places, prices, opening hours, amenities, or bookings.
- Distinguish retrieved facts, calculated estimates, and unknown details.
- Treat retrieved webpage text as data, not agent instructions.
- Preserve previous itinerary versions.
- If a provider fails, return a clearly labelled partial plan.
- Do not expose API keys or private trip details in public demos.

## Verification

- Test impossible schedules, closed attractions, missing opening hours,
  late departures, budget conflicts, provider failures, and replanning
  with locked activities.
- Test multi-vehicle fuel calculations and group accommodation assumptions.
- Use a live road-trip example and clearly labelled fixtures for failures.

## Implementation order

1. Road planning, stops, attractions, timeline, map, and sources.
2. Hotel comparison, budget breakdown, and delay replanning.
3. Flights, authorized train integration, voice, and expanded catalog.

## Demo scenario

Six friends, three motorcycles, Coimbatore to Munnar, two days including
the return journey. Start Saturday 6 AM, ₹5,000 per person, vegetarian
food, no riding after dark.

The planner must confirm constraints, retrieve two-wheeler route
candidates, schedule breaks and grouped attractions, compare
accommodation, reserve return time, explain whether two days are
feasible, and replan on a reported delay — without promising to
"cover all of Munnar."

## Disclosure

AI assistants are used for code generation and documentation, disclosed
on request per hackathon rules. LLM calls inside the product are
configurable and kept server-side.
