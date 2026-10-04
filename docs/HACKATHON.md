# SerpApi India Hackathon submission preparation

Verified against the official rules and dashboard on 2026-10-04.

- Public repository: https://github.com/praneeth-7606/trippilot-india
- Track: Travel & Local Discovery
- Confirmed referral: **HydPy**. Entry type: **solo**.
- Deadline: **2026-10-10 23:59 IST**
- Dashboard: https://serpapi.github.io/serpapi-india-hackathon-2026/submit.html
- Rules: https://serpapi.github.io/serpapi-india-hackathon-2026/rules.html
- Terms: https://serpapi.github.io/serpapi-india-hackathon-2026/terms.html

## Draft form text

**Project name:** TripPilot India

**Description:** A constraint-aware road-trip planner for Indian groups travelling by car or motorcycle. It brings together outbound and return routes, practical stop candidates, destination attractions, an editable timeline and clear feasibility conflicts. SerpApi Maps and Directions contribute route/place evidence, while Google Search supplies public visitor-information links. Python schedules and validates the itinerary through a LangGraph workflow. Users can lock activities, report delays, and review resulting conflicts without rewriting prior itinerary versions. The first scenario is six friends on three motorcycles travelling from Coimbatore to Munnar and back over two days.

**AI disclosure:** OpenCode, powered by OpenAI gpt-6.1-sol, assisted with project planning, code generation, debugging, tests and documentation. No in-product LLM calls have been enabled in this Phase 1 preview. Deterministic Python performs the scheduling and feasibility checks.

**Existing project:** This repository was created during the hackathon; its first commit and subsequent implementation history are public. Verify this answer if earlier project code is incorporated.

## Remaining participant declarations

- GitHub sign-in in the event dashboard is required. CLI authentication is not dashboard authentication.
- A draft requires project name, description and the actual community/source. **HydPy** was confirmed by the participant.
- The participant chose to fill the personal fields themselves. Do not infer their phone number or completed years of experience.
- Final entry needs name, email, mobile, occupation, years of experience, track, team details if any, AI disclosure and Rules/Terms acceptance.
- A saved draft is **not** a submitted entry. Select **Submit project** after all fields are complete.
- This file does not claim registration, draft creation or final submission has happened.

## Under-three-minute local recording outline

1. 0:00–0:25 — show the group, motorcycles, outbound/return dates, budget and daylight limit.
2. 0:25–1:10 — build the itinerary; show real route/place evidence from SerpApi, mode, source timestamps, planned stops and return deadline.
3. 1:10–1:55 — inspect conflicts/exclusions; lock an activity and report a delay; show preserved locked time and new itinerary version.
4. 1:55–2:35 — show the map, assumptions, source links and printable summary.
5. 2:35–2:50 — show reproducible repository setup and name limitations honestly.

Use a publicly accessible video link that opens in an incognito window. The rules require a local screen recording under three minutes; narration and polished editing are optional.

Live Maps/Directions/Search calls have now been verified and a **48.4-second local screen recording** is available in `docs/trippilot-live-demo.webm`. The recording shows actual app interaction without mocked responses. A publicly accessible hosted video link and its incognito check are required before final submission. Hotel/flight searches remain future work.
