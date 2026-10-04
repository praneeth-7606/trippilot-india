# TripPilot India

**A group road-trip planner that checks whether the journey actually fits.**

Built for the [SerpApi India Hackathon 2026](https://serpapi.github.io/serpapi-india-hackathon-2026/) · **Travel & Local Discovery**.

## Phase 1 preview

- Structured trip form: origin, destination, outbound/return dates and times, group size, car/motorcycle, vehicle count/mileage, budget, pace, daylight limits and must-visits.
- LangGraph workflow: provider research → route-stop suggestions → deterministic scheduling and feasibility validation.
- SerpApi Maps/Directions/Search adapters with timeouts, a search budget and response caching. Directions uses `travel_mode=9` for motorcycles and `0` for cars.
- Day-by-day itinerary, source evidence, exclusions, route alternatives, weather and a **partial** cost estimate.
- Leaflet/OpenStreetMap map synchronized with timeline selection. Waypoint lines are schematic, not turn-by-turn geometry.
- Lock/skip activities, apply a 90-minute delay, keep prior versions, share a read-only link and print a summary.

**Default demo is synthetic.** With no backend SerpApi key, the Coimbatore ↔ Munnar scenario uses explicitly labelled generated test data. It is not a recording of real search results. Other routes require a live key. Live calls have not yet been verified in this repository.

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

- Phase 1 accepts one road destination and up to 16 days in `Asia/Kolkata`. Natural-language parsing and an in-product LLM provider are not wired yet.
- Trip records and versions are **in memory**, and disappear on backend restart. PostgreSQL persistence is Phase 2 work. Sharing works only while that backend retains the trip.
- Stop placement uses route-step coordinates and approximate off-route travel time. Destination hops also use geometric estimates, not extra Directions calls. Dense route geometry, routed detour validation and overnight waypoint towns are future work.
- Published hours may be incomplete; weekday/holiday closure handling and complete day-specific hours still need expansion.
- Fuel calculations include vehicle counts. Fuel-stop suggestions assume a full tank at each leg's start; tank-state tracking through the entire trip and availability confirmation are not implemented.
- Cost figures are **fuel/food subtotals** based on displayed assumptions; accommodation, tickets, tolls and local travel are excluded. Hotel/flight searches and actual bookings are not implemented.
- Delay handling shifts unlocked items and reports resulting conflicts; it does not claim to resolve every infeasible delay automatically.
- Local preview only: authentication, durable storage and public-deployment access controls need implementation before handling real private trips on the internet.

## Hackathon preparation and AI disclosure

[Submission preparation, draft text and demo outline](docs/HACKATHON.md). A public repository is ready; dashboard registration/draft/final submission and the demo video are still pending.

**OpenCode, powered by OpenAI gpt-6.1-sol**, assisted with planning, code, tests, debugging and documentation. The current application schedules deterministically; no in-product model calls are enabled. Disclose AI assistance in the event form as well.

MIT licence. Map attribution is displayed in the application; third-party libraries retain their respective licences.
