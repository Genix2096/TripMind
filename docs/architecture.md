# Architecture (Phase 1 foundation)

AgentTrip is live-only, database-free, and quota-conscious. Phases 2–4 add agents, UI and handover.

```
backend/app
├── core/        config (settings), errors, authorization (per-run call budget), logging (redaction)
├── models/      typed contracts: TripState, flights, hotels, geo, weather, common (Provenance, SearchResult)
├── providers/   one adapter per capability; the only code that talks to the network
│   ├── serpapi/   flights.py, hotels.py (separate parsers) + common.py (single shared credential)
│   ├── geoapify/  places.py (+ geocoding), routing.py
│   ├── openweather/adapter.py
│   └── groq/client.py
├── planning/    deterministic logic: budget.py, constraints.py, weather_coverage.py
└── api/ + main.py   FastAPI: /api/health, /api/config/status only (no provider calls)
```

## How the non-negotiable rules are enforced

| Rule | Mechanism |
|---|---|
| No fake data / no fallback | No mock, demo or local-data code exists in `app/`. Failures raise typed `ProviderError`s; `SearchResult` represents only *successful* searches (`ok`/`empty`). Tests scan runtime code for demo/fallback flags and fixture imports. |
| Explicit search control | Every adapter method requires a `SearchAuthorizer` and calls `authorize()` right before the single HTTP request. Authorizers are created per user-initiated planning run (Phase 2/3). Nothing runs at startup, on health checks, or at import time. |
| Bounded usage | Per-capability call limits per run, duplicate identical searches blocked, closed runs rejected. **No retries anywhere** (`ProviderHttp` makes one request). |
| Missing credentials | Checked *before* authorization/network: raises `MissingCredentialsError`, uses no quota, app still starts. |
| Shared SerpApi key | `providers/serpapi/common.get_serpapi_key` is the only reader of `SERPAPI_API_KEY`; both adapters use it. |
| Truthful data | Optional fields stay `None`; `missing_fields` lists absent ones; hotel nightly/total never derived from each other in adapters; unparseable price text is kept as `display_text` with no amount. |
| Provenance | Each entity has `Provenance` (provider, capability, retrieved_at, provider_id, source_url, search_id, raw). `SearchMeta` records sanitized request params and provider limitations. |
| Budget honesty | `planning/budget.py`: five cost classes, unknown ≠ 0, status `incomplete_costs_unknown` unless all expected categories are known, no currency conversion. |
| Constraints | `planning/constraints.py`: *violation* only when provider data proves it; missing data is *unverifiable*. |
| Secrets | `SecretStr` settings, key redaction in error text and logs, httpx URL logging silenced, no key ever returned by the API. |
| State isolation | No module-level mutable state; run state lives in a per-run `SearchAuthorizer` (and later typed run objects). |
| No database | No DB dependency/config/code; a test asserts this. |

## Provider decisions & limitations (summary — details in `api_integrations.md`)

* SerpApi hotels has **no room-count parameter**; results are for the searched adults/children occupancy.
* SerpApi flights does **not state** whether `price` is per traveler or for all; budget code treats this as unknown unless the user states an assumption.
* Round-trip flight results show the outbound leg + round-trip price; return-leg details need an extra explicit search with `departure_token`.
* OpenWeather free 2.5 forecast reaches ~5 days; later dates are reported as unavailable.
* Geoapify opening hours are raw OSM strings (parsing/validation is Phase 2 scheduling work).
