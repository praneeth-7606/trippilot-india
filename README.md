# TripPilot India

**A group road-trip planner that checks whether the journey actually fits.**

Built for the [SerpApi India Hackathon 2026](https://serpapi.github.io/serpapi-india-hackathon-2026/) · **Travel & Local Discovery**.

## Phase 1 preview

- Structured trip form: origin, up to 4 destinations in visit order, outbound/return dates and times, group size, car/motorcycle, vehicle count/mileage, budget, pace, daylight limits and must-visits.
- Optional Mistral Trip Copilot: turns a natural-language road-trip description into a validated draft or asks for the missing constraints. It never invents routes, prices or bookings.
- Vacation chat agent: multi-turn conversation that collects a multi-stop holiday intent and builds the routed plan with per-city stays. Drafts validate against the same typed contract.
- LangGraph workflow: provider research → route-stop suggestions → deterministic scheduling and feasibility validation.
- SerpApi Maps/Directions/Search adapters with timeouts, a search budget and response caching. Directions uses `travel_mode=9` for motorcycles and `0` for cars.
- Route choice: every plan lists the available routes with distance/time; picking one rebuilds stops, stays and costs around it.
- Day-by-day itinerary, source evidence, exclusions, route alternatives, per-city hotel search links, weather and a **partial** cost estimate.
- Leaflet/OpenStreetMap map synchronized with timeline selection. Waypoint lines are schematic, not turn-by-turn geometry.
- Lock/skip activities, apply a 90-minute delay, keep prior versions, share a read-only link and print a summary.

**Live workflow verified.** The Coimbatore ↔ Munnar motorcycle scenario was tested against real SerpApi Maps, Directions and Google Search responses. Without a backend key, the application still offers explicitly labelled synthetic fixtures. Synthetic fixtures are not recordings of real results.

[Local live demo recording (48.4 seconds)](docs/trippilot-live-demo.webm) — shows the running app, real route/stop evidence, a locked activity and delay handling. No API key is visible or included in the recording.

## Run locally on Windows

Requires Python 3.12+ and Node 22.12+ or 24+. Run these from the repository folder.

**Terminal 1 — backend**

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
# Optional: create backend/.env using backend/.env.example and add your key locally.
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

To use `backend/.env` with the command above, add `--env-file backend/.env`. Alternatively, run `uvicorn app.main:app` from `backend/`. Never commit an actual `.env` file.

**Terminal 2 — frontend**, working directory `frontend/`:

```powershell
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Backend docs: **http://127.0.0.1:8000/docs**.

### Live searches

Set `SERPAPI_API_KEY` on the backend and `TRIPPILOT_FIXTURES=0`. Never put secrets in frontend variables. The workflow issues Maps/Directions requests plus a Google (`engine=google`) visitor-information lookup; the default per-plan search budget is 40 uncached requests. Cached synthetic responses and live responses are separated.

### Natural-language intake

Set `MISTRAL_API_KEY` and an account-available `MISTRAL_MODEL` in `backend/.env`. The copilot uses Mistral JSON mode only to create a `TripRequest` draft and clarification questions; the existing Pydantic validators and deterministic planner remain authoritative. A missing or rate-limited Mistral account leaves the structured form fully usable.

Open-Meteo is keyless; forecast data is unavailable beyond its supported window. Directions navigation links open Google Maps; explicitly confirm motorcycle mode in the navigation application.

## Verification

Backend, working directory `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest -q
```

Frontend, working directory `frontend/`:

```powershell
npm run build
npx playwright install chromium
# With both development servers running:
node scripts/test-browser.mjs
# Alternatively use installed Edge on Windows:
$env:BROWSER_CHANNEL = 'msedge'
node scripts/test-browser.mjs
```

Regenerate synthetic fixtures from `backend/`: `.venv/Scripts/python.exe fixtures/generate.py`.

## Container configuration

`docker compose up --build` configures the web application at `http://localhost:8080`, FastAPI and Redis. Compose configuration has been validated; container execution has not been tested because Docker Desktop's Linux engine is unavailable on the development machine.

## Current boundaries

- Trips accept 1–4 road destinations in visit order and up to 16 days in `Asia/Kolkata`. Trains, flights and live hotel/flight booking remain later slices; stays use your estimates plus hotel search links.
- Trip records and versions are **in memory**, and disappear on backend restart. PostgreSQL persistence is Phase 2 work. Sharing works only while that backend retains the trip.
- Stop discovery is biased to the route's geometry midpoint. Selected road stops are verified with actual Directions legs; the plan shows the extra driving time versus the direct route. If verification fails, estimates remain labelled partial. Destination hops still use geometric estimates. Overnight waypoint towns are future work.
- Weekly listing hours are checked against the actual trip weekday. Missing hours, split sessions and holiday exceptions still need confirmation rather than being inferred from an "open now" badge.
- Fuel calculations include vehicle counts. Fuel-stop suggestions assume a full tank at each leg's start; tank-state tracking through the entire trip and availability confirmation are not implemented.
- Cost figures include fuel/food assumptions plus any accommodation, toll, ticket and local-transport values supplied by the traveller. They are not live hotel, toll or ticket quotes; hotel/flight searches and bookings are not implemented.
- Delay handling shifts unlocked items and reports resulting conflicts; it does not claim to resolve every infeasible delay automatically.
- Local preview only: authentication, durable storage and public-deployment access controls need implementation before handling real private trips on the internet.

## Hackathon preparation and AI disclosure

[Submission preparation, draft text and demo outline](docs/HACKATHON.md). Public code and a verified local demo are ready. Dashboard draft/final submission still depend on participant sign-in and personal fields.

**OpenCode, powered by OpenAI gpt-6.1-sol**, assisted with planning, code, tests, debugging and documentation. The current application schedules deterministically; no in-product model calls are enabled. Disclose AI assistance in the event form as well.

MIT licence. Map attribution is displayed in the application; third-party libraries retain their respective licences.
