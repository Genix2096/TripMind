# AgentTrip

**Phase 4 Completed**: The frontend now parses and renders structured Pydantic models directly from the backend multi-agent orchestrator. Provider failures and success states are rigorously tracked without fabricating missing data. Ready for final manual live-testing handover.


AI multi-agent travel planner using **live provider data only** (SerpApi Google Flights + Hotels, Geoapify,
OpenWeather, Groq). No database, no demo mode, no fallback data.

**Status: Phase 1 of 4 complete (backend foundation + provider adapters).** Agents, frontend and the full
README/manual-test handover follow in Phases 2–4. No live API integration has been verified yet.

## Backend setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
copy .env.example .env   # then fill in keys; .env is git-ignored
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```
The server starts without any keys; a capability whose key is missing returns a clear configuration error.
Starting the server, `/api/health` and `/api/config/status` never call an external provider.

## Local tests (no network, no quota)
```powershell
cd backend
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check app tests --select E9,F,B
```
Tests block non-loopback sockets and use synthetic payloads kept only under `backend/tests/`.

See [docs/architecture.md](docs/architecture.md), [docs/api_integrations.md](docs/api_integrations.md),
[docs/manual_testing.md](docs/manual_testing.md).
