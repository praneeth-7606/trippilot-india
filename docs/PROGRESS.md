# Build checkpoint — 2026-10-04

## Delivered preview

The road-trip vertical slice runs end to end locally: structured input → LangGraph research/stops/schedule workflow → validated timeline/map → activity locks/skips and delay versions → read-only sharing and printing.

The default Coimbatore/Munnar scenario uses synthetic inputs. No live search capture, actual reservation, final hackathon submission or public application deployment is claimed.

## Verification evidence

- Backend: **15 tests passed**, no warnings in the final run.
- Python dependency check: no broken installed requirements.
- Frontend: TypeScript checks and Vite production build passed.
- Browser: real headless Edge tested create/plan, lock, delay preserving locked time, read-only sharing, and overflow at 320/768/1024/1440 px; no page exceptions.
- Production frontend dependency audit: zero reported vulnerabilities.
- Compose configuration valid; Docker runtime untested because the Linux engine is unavailable.

Important fixes verified by regression tests: all vehicles count toward fuel estimates; per-person budgets convert to group limits; cached synthetic/live data stay separate; zero-route responses fail explicitly; itinerary edits/replans preserve old versions; date rollover is retained; excluded must-visits raise conflicts; read-only recipients do not receive the private trip-edit identifier.

## Next implementation slice

1. Live API verification and local demo recording are now complete (see checkpoint below).
2. Road-stop legs now use routed measurements and weekly listing closures are handled. Destination-leg routing and complete fuel-state tracking remain.
3. Add PostgreSQL persistence, hotel comparison and more capable conflict-resolving replanning.
4. Select the in-product LLM provider and add natural-language clarification against the existing typed request.
5. Complete dashboard draft/final submission using the real community/source and participant declarations; record a local live demo under three minutes.

For an interruption: preserve the repository and use the README's setup commands. Trip records are currently ephemeral; recreating a trip is expected after a backend restart.

## Live checkpoint — October 5, 2026 IST

- Backend key is present in the Git-ignored local `.env`; no credential is printed or committed.
- Real two-wheeler direct route: **150.3 km / 232 min**.
- Verified outbound stop chain: **152.7 km / 254 min**, **+22 min** versus direct, excluding stop dwell time.
- Verified return stop chain: **161.3 km / 265 min**, **+21 min** versus direct.
- Live plan reports `ready` with explicit warnings for attractions lacking published hours. The run made 15 provider requests within the 40-request plan budget; SerpApi's own cache may make some requests free.
- Broad stop queries returned no results. Replaced them with geographically biased category searches; fixed an additional clustered-break bug exposed by real result density.
- **18 tests pass**. Live browser workflow and production frontend build pass; no page exceptions at the checked viewport sizes.
- Recorded a genuine local-screen video: **48.4 seconds**, **1280×900**, WebM/VP8. A frame was decoded and visually checked before publication.
- Participant confirmed **HydPy**, **solo**, and manual entry of personal fields.
- GitHub dashboard authentication, saved draft and final submission must be verified separately; they are not implied by code/video completion.
