<USER_REQUEST>
# AGENTTRIP — COMPLETE PROJECT RESTART PROMPT

## Project Overview

You are a senior AI engineer, Python backend architect, React frontend developer, API integration specialist, and autonomous multi-agent systems engineer.

We are building **AgentTrip**, an AI-powered, multi-agent travel planning application that generates personalized travel itineraries using real-world, live external data.

This is a complete restart of the project. We are starting from scratch in a brand-new folder in Antigravity. Do not reuse, copy, or depend on code from any previous version.

The objective is to build a reliable, genuinely agentic travel planner that understands natural-language requests, researches flights and hotels, discovers attractions, evaluates routes and weather, validates budgets, and synthesizes feasible itineraries.

This must be a real working application, not a static demonstration or a chatbot that invents travel recommendations.

The project must be implemented in exactly **four major phases**, as defined in this prompt.

---

# 1. NON-NEGOTIABLE PROJECT RULES

These rules take priority over convenience, shortcuts, and default development practices.

## 1.1 No fake data in production

The application must never use:

- Mock flights or hotels.
- Fabricated flight or hotel prices.
- Fake attraction listings.
- Invented weather information.
- Fake opening hours, ratings, or amenities.
- Randomly generated search results.
- Hardcoded sample itineraries presented as real recommendations.
- Predefined destination datasets used as search results.
- LLM-generated substitutes for missing API responses.
- Simulated availability or booking links.
- Local datasets used as fallback travel information.

Every externally sourced travel fact must originate from a legitimate provider response.

The LLM may interpret, rank, compare, and explain retrieved information. It must never manufacture missing travel facts.

If a provider returns incomplete data, represent missing fields accurately. If a search returns no results, report that no results were found. If a provider fails, report the failure.

An incomplete but truthful itinerary is preferable to a complete itinerary containing invented information.

**Testing fixtures are allowed only inside isolated automated tests.** They must never enter the production response path or appear to users as actual travel results.

## 1.2 Live-only operation

AgentTrip must use real external APIs for live travel information.

There must be no demo mode, offline recommendation mode, fake-data mode, or automatic fallback to locally generated travel information.

Do not implement:

- `APP_MODE=demo`
- `USE_MOCK_DATA=true`
- `ENABLE_DEMO_DATA=true`
- `LIVE_TOOL_FALLBACK_TO_LOCAL=true`

Do not silently switch to another provider or data source when an API fails.

When a provider fails:

1. Return an explicit, meaningful error.
2. Identify the affected provider or capability.
3. Distinguish failure from a successful search with zero results.
4. Never substitute fabricated results.
5. Allow the user to retry manually.

## 1.3 I will perform all live API testing

**I will manually perform every live API test because our available search quota and API credits are limited.**

Antigravity must not independently consume these credits.

You must not:

- Execute real flight searches during development.
- Execute real hotel searches during development.
- Execute real attraction or routing searches during development.
- Execute real weather queries during development.
- Test API keys by making real requests.
- Run automated tests that contact external APIs.
- Generate live itineraries automatically to verify the application.
- Make external requests during application startup.
- Trigger searches during frontend page loading or component mounting.
- Make external requests from health checks.
- Perform hidden or automatic retries against quota-limited endpoints.
- Run background jobs that consume API credits.
- Claim that a provider integration is live-verified when it has only passed local tests.

Your responsibility is to implement the code, inspect available official documentation, write local tests, verify internal logic, and prepare manual testing instructions.

Only I will initiate live searches through the running application's interface.

If you are uncertain whether an operation consumes an API request or quota, do not execute it. Inspect or implement the code locally instead.

## 1.4 Explicit control over external searches

External search requests must be initiated only through an explicit user action in the planning workflow.

The frontend must not automatically initiate searches on page load.

The backend must not make external requests simply because the server starts.

The agent orchestration system must require explicit authorization before invoking external search tools.

Do not add hidden API calls, speculative searches, background refreshes, or automatic retries.

The application should make only the provider requests necessary for the user's explicitly initiated planning operation.

## 1.5 Limited and controlled API usage

Implement efficient request management:

- Avoid unnecessary duplicate searches.
- Avoid repeating identical searches within a planning run.
- Use explicit cache keys and freshness rules if caching is implemented.
- Preserve provider identity and retrieval timestamps.
- Never represent stale cached results as current live data.
- Do not automatically refresh expired cached results.
- Do not retry quota-related errors automatically.
- Avoid speculative searches.
- Bound all agent tool calls and planning iterations.

Caching is optional. If implemented, it must preserve source and freshness information and must never become a source of fabricated or misleadingly current data.

## 1.6 No database in the initial version

**We are not using a database in this version of AgentTrip.**

Do not install, configure, or implement:

- SQLite.
- PostgreSQL.
- MySQL.
- MongoDB.
- Supabase database.
- Any other database system.

Do not create database schemas, ORM models, database repositories, migration scripts, connection pools, or database configuration.

Do not add a database merely to store trip history.

If persistent cloud storage or another database-dependent feature becomes necessary in the future, discuss it with me first. We may add one in a later version, but it is explicitly outside the current scope.

For the initial implementation:

- Use in-memory state for an active planning session.
- Use React state for live UI state.
- Use browser local storage for lightweight trip history and preferences.
- Consider IndexedDB only if larger structured browser-side storage becomes necessary.

Browser storage is not a database server and must not be used to pretend that cloud persistence exists.

Do not promise cross-device synchronization.

## 1.7 No unnecessary technology changes

Use the agreed stack and providers.

Do not replace an API simply because another provider is easier to integrate.

Do not introduce additional paid providers or API keys without discussing the change with me first.

---

# 2. PROJECT OBJECTIVE

AgentTrip is a natural-language travel planning system that combines multiple cooperating AI agents with deterministic planning logic.

A user might enter:

"I want to travel from Chennai to Goa for four days with a budget of ₹25,000 per person. I prefer comfortable hotels, beaches, local attractions, and minimal travel time between places."

AgentTrip should:

1. Understand the request.
2. Extract travel constraints.
3. Ask for missing mandatory information.
4. Search for real flights.
5. Search for real hotels.
6. Discover relevant real-world attractions.
7. Retrieve relevant route information.
8. Retrieve weather information when supported for the requested dates.
9. Compare the actual returned candidates.
10. Validate costs and scheduling feasibility.
11. Replan within strict limits when valid alternatives exist.
12. Produce a coherent, day-wise itinerary using retrieved data.
13. Explain its decisions and limitations.
14. Identify unavailable information rather than inventing it.

Support destinations beyond any predefined list, subject to the external providers' capabilities.

## User inputs

Support the following where relevant:

- Origin and destination.
- Departure and return dates.
- Trip duration.
- Number of travelers.
- Number of adults and children.
- Children's ages when required by a provider.
- Hotel rooms and occupancy.
- Total budget or per-person budget.
- Budget currency.
- Preferred airline or cabin class.
- Hotel category and accommodation preferences.
- Preferred attractions and activities.
- Food preferences.
- Mobility requirements.
- Preferred travel pace.
- Maximum acceptable travel time.
- Interests such as beaches, nature, history, adventure, shopping, culture, and nightlife.
- Required and excluded activities.
- Other constraints expressed in natural language.

Do not force users to select destinations from a hardcoded city list.

Ask clarification questions when mandatory information is missing or contradictory. Avoid unnecessary searches before the requirements are sufficiently clear.

---

# 3. TECHNOLOGY STACK

## 3.1 Frontend

Use:

- React.
- Vite.
- TypeScript.
- Tailwind CSS.
- Responsive desktop and mobile layouts.

Build a professional interface with reusable components, clear progress indicators, source transparency, and useful error messages.

## 3.2 Backend

Use:

- Python.
- FastAPI.
- Pydantic for request and response validation.
- Modular services and provider adapters.

Do not add a database.

Do not place the entire application in a single large file.

## 3.3 LLM and reasoning

Use Groq for LLM-based reasoning and agent orchestration.

Environment variables:

- `GROQ_API_KEY`
- `GROQ_MODEL`

Select a currently supported Groq model with the required tool-calling or structured-output capabilities. Inspect available documentation before selecting the model.

Do not hardcode an outdated model name throughout the application.

The LLM is responsible for natural-language understanding, preference interpretation, reasoning, agent coordination where appropriate, and explanations.

It is not the source of truth for live flights, hotel prices, attractions, weather, or routes.

Use deterministic Python code for calculations and hard constraints.

## 3.4 External APIs

Use these agreed providers:

**A. SerpApi — Flights and Hotels**

SerpApi handles both flight and hotel searches using the same API key.

- Flights: SerpApi Google Flights.
- Hotels: SerpApi Google Hotels.

**B. Geoapify — Places and Routing**

Use Geoapify for real-world place discovery and supported routing and distance calculations.

**C. OpenWeather — Weather**

Use OpenWeather for current weather and supported date-specific forecasts.

**D. Groq — AI reasoning**

Use Groq for LLM reasoning and the agentic planning system.

Do not add other external travel providers without discussing the change with me first.

---

# 4. EXTERNAL API INTEGRATION REQUIREMENTS

## 4.1 SerpApi Google Flights

Implement a dedicated flight adapter using the officially documented Google Flights search engine.

Environment variable:

`SERPAPI_API_KEY`

Support provider-appropriate parameters for:

- Origin and destination.
- Departure date.
- Return date for round trips.
- One-way and round-trip travel.
- Passenger count.
- Cabin class.
- Currency where supported.
- Relevant connection and duration filters where supported.

Normalize actual returned flight information, including available fields for:

- Airline.
- Departure and arrival airports.
- Departure and arrival times.
- Journey duration.
- Number of stops.
- Connections.
- Actual returned price.
- Flight details.
- Booking or provider links where supplied.
- Source attribution.
- Retrieval timestamp.

Do not assume every response contains every field.

Do not invent flight numbers, prices, schedules, baggage allowances, booking links, or availability.

Do not assume a search result guarantees that a fare will remain available at checkout.

## 4.2 SerpApi Google Hotels

Implement a dedicated hotel adapter using the officially documented Google Hotels search engine.

Use the exact same `SERPAPI_API_KEY` configured for flights.

Support relevant parameters such as:

- Destination or hotel search location.
- Check-in date.
- Check-out date.
- Number of adults.
- Children and their ages where supported.
- Room count where supported.
- Currency and locale where supported.
- Hotel rating, property type, or other supported filters.

Normalize actual returned hotel information, including:

- Hotel name.
- Address or location.
- Coordinates when supplied.
- Nightly price when explicitly supplied.
- Total stay price when explicitly supplied.
- Rating and review count.
- Amenities.
- Property type.
- Images.
- Provider-supplied hotel or booking links.
- Cancellation details when supplied.
- Availability information when supported by the returned data.
- Retrieval timestamp.

Do not assume nightly and total-stay prices are interchangeable.

Do not calculate an unverified nightly rate from an ambiguous total or price field.

Do not invent taxes, fees, cancellation policies, room availability, ratings, or amenities.

Clearly distinguish hotel search results from confirmed reservations.

Google Hotels search results do not guarantee a final checkout price or a confirmed room.

## 4.3 Geoapify Places

Use Geoapify's documented place discovery functionality to retrieve real attractions and points of interest.

Environment variable:

`GEOAPIFY_API_KEY`

Use appropriate geographic and category filters to find relevant places.

Retrieve supported fields such as:

- Place name.
- Category.
- Address.
- Coordinates.
- Descriptive information.
- Opening hours when provided.
- Other relevant metadata.

Do not invent attraction names, ratings, entrance fees, opening hours, or descriptions presented as verified facts.

If opening hours or entrance fees are unavailable, identify them as unavailable.

## 4.4 Geoapify Routing

Use Geoapify's supported routing functionality to estimate journeys between selected itinerary stops.

Retrieve supported details, including:

- Distance.
- Estimated travel duration.
- Route geometry where available.
- Travel mode.

Use real coordinates and valid route requests.

Do not invent route durations, distances, road conditions, or travel times.

If the required routing mode is unsupported or a route cannot be calculated, report that limitation.

## 4.5 OpenWeather

Use OpenWeather for current weather and supported forecasts.

Environment variable:

`OPENWEATHER_API_KEY`

Use the appropriate API based on requested dates and actual forecast availability.

Rules:

- Do not present current weather as a future forecast.
- Do not fabricate forecasts outside the supported forecast horizon.
- Do not substitute invented weather when a request fails.
- Clearly indicate when a forecast is unavailable.
- Preserve retrieval timestamps and relevant forecast timestamps.

## 4.6 Shared configuration and separate adapters

Create these provider modules:

- `SerpApiFlightsAdapter`
- `SerpApiHotelsAdapter`
- `GeoapifyPlacesAdapter`
- `GeoapifyRoutingAdapter`
- `OpenWeatherAdapter`
- `GroqLLMClient`

The flight and hotel adapters must share the same SerpApi credential source but retain separate request parameters, parsing logic, and error handling.

Do not reuse a flight response parser for hotel responses.

---

# 5. MULTI-AGENT ARCHITECTURE

AgentTrip must implement genuine multi-agent planning.

A single LLM prompt that writes an itinerary without retrieving and validating data does not satisfy this requirement.

Implement a central Planning Coordinator and eight specialist agents.

## Agent 1: Travel Request Understanding Agent

Responsibilities:

- Interpret the user's natural-language request.
- Extract structured travel requirements.
- Identify mandatory constraints and preferences.
- Detect missing or contradictory information.
- Ask clarification questions where needed.
- Produce a validated `TripState`.

This agent must not invent missing user preferences.

## Agent 2: Flight Research Agent

Responsibilities:

- Search through the SerpApi Google Flights adapter when authorized by the coordinator.
- Compare real flight candidates.
- Evaluate price, duration, stops, and schedule suitability.
- Return structured candidate information.
- Preserve source and retrieval metadata.
- Report provider errors and empty results accurately.

It must never generate a fictional flight.

## Agent 3: Hotel Research Agent

Responsibilities:

- Search through the SerpApi Google Hotels adapter.
- Respect destination, dates, occupancy, budget, and accommodation preferences.
- Compare actual returned hotel candidates.
- Evaluate price information carefully.
- Preserve source and retrieval metadata.
- Report missing prices and unsupported availability information.

It must never invent a hotel, room, or price.

## Agent 4: Places and Activities Agent

Responsibilities:

- Discover actual attractions using Geoapify.
- Match places to user interests.
- Evaluate geographic proximity.
- Retrieve opening hours where supported.
- Exclude unsuitable places only when evidence supports doing so.
- Return source-backed attraction candidates.

It must not create fictional activities to fill gaps in the itinerary.

## Agent 5: Routing and Scheduling Agent

Responsibilities:

- Use Geoapify routing functionality.
- Estimate travel times between selected stops.
- Organize attractions into feasible daily sequences.
- Account for verified opening hours and travel times.
- Minimize unnecessary travel where appropriate.
- Detect scheduling conflicts.
- Identify missing route information.

Do not claim a schedule is feasible when essential travel information is missing.

## Agent 6: Weather Agent

Responsibilities:

- Retrieve relevant current weather or supported forecasts.
- Identify weather-related itinerary risks using actual returned information.
- Suggest appropriate adjustments when supported by evidence.
- Explain when the requested dates fall outside forecast availability.

It must not invent weather conditions.

## Agent 7: Budget and Constraint Validation Agent

Use deterministic Python calculations for budget validation and hard constraints.

Responsibilities:

- Validate the user's budget.
- Calculate supported flight and hotel totals.
- Include known taxes and fees only when supported by provider data.
- Account for other costs only when actual source-backed prices or explicitly labeled user inputs are available.
- Distinguish confirmed costs, calculated totals, estimates, and unknown costs.
- Identify missing budget categories.
- Detect hard-constraint violations.
- Prevent unsupported claims that a trip fits within budget.
- Reject infeasible candidates when evidence establishes that they violate mandatory requirements.

Never assume unknown costs are zero.

Never invent attraction fees, meal costs, or local transport costs to make a budget appear feasible.

If the full budget cannot be calculated, show the known subtotal and clearly identify missing costs.

## Agent 8: Itinerary Synthesis Agent

Responsibilities:

- Combine validated flights, hotels, attractions, routing, and weather information.
- Generate a coherent day-wise itinerary.
- Preserve source provenance.
- Explain why particular options were selected.
- Respect the user's mandatory constraints.
- Clearly distinguish provider facts from recommendations and estimates.
- Report limitations and unresolved uncertainties.

The LLM must not introduce fabricated entities or facts during synthesis.

## Planning Coordinator

The coordinator controls the overall workflow.

It must:

1. Receive the validated `TripState`.
2. Determine what data is required.
3. Decide which specialist agents are necessary.
4. Authorize the required external tool calls.
5. Collect structured results.
6. Detect missing information, conflicts, and provider errors.
7. Compare valid candidates.
8. Invoke deterministic budget and constraint validation.
9. Replan when useful alternatives exist.
10. Enforce strict limits on agent steps and external requests.
11. Stop when constraints are satisfied or the available evidence is insufficient.
12. Produce the final itinerary with source-backed explanations.

Do not allow agents to independently trigger unlimited API searches.

Do not implement infinite agent loops.

Do not repeat failed external searches automatically.

If a required provider fails, explain which parts of the plan could not be completed.

## Agent state without a database

All planning state must be maintained in memory for the active planning operation and passed between agents as typed objects.

Use React state for active UI state.

Use browser storage for optional local trip history.

Do not introduce a database or database-like server persistence layer.

Ensure that separate users or simultaneous planning requests cannot accidentally share mutable agent state.

---

# 6. DATA FLOW AND SOURCE OF TRUTH

Implement typed, structured data contracts between the frontend, backend, agents, and provider adapters.

The main workflow should be:

User Request → Request Understanding → TripState Validation → Planning Coordinator → Authorized Live Searches → Structured Provider Results → Candidate Comparison → Budget and Constraint Validation → Bounded Replanning → Itinerary Synthesis → User Review

Every external entity must preserve source provenance.

For each flight, hotel, attraction, weather record, and route, retain relevant metadata:

- Provider name.
- Retrieval timestamp.
- Provider identifier when available.
- Source URL when supplied.
- Original returned fields as appropriate.
- Freshness or validity information when relevant.

Never fabricate a source URL.

Never confuse an LLM-generated explanation with a provider-returned fact.

The application must be able to trace important external claims back to the relevant provider response.

Do not represent an AI recommendation score as an externally supplied rating.

---

# 7. BUDGET, RANKING AND FEASIBILITY

The system must make meaningful decisions rather than simply sorting all results by price.

Consider:

- Total known cost.
- Journey duration.
- Number of flight stops.
- Hotel suitability.
- Geographic proximity of attractions.
- User preferences.
- Scheduling feasibility.
- Weather risks when reliable forecasts are available.

Use deterministic ranking and constraint checks where appropriate. Use the LLM to interpret preferences and explain trade-offs.

Every cost must be classified appropriately:

1. Verified provider price.
2. Calculated total based on verified prices.
3. Explicit user-provided assumption.
4. Estimate with a documented basis.
5. Unknown or unavailable cost.

Do not silently assume unknown costs are zero.

Do not guarantee that a trip is within budget when essential costs are unknown.

If no suitable option satisfies the mandatory constraints, explain why and suggest evidence-based alternatives, such as:

- Adjusting travel dates.
- Increasing the budget.
- Selecting a different accommodation category.
- Relaxing an optional preference.
- Considering a different route or destination.

Only present alternatives supported by the available evidence.

---

# 8. FRONTEND REQUIREMENTS

Build a professional, responsive interface using React, Vite, TypeScript, and Tailwind CSS.

## 8.1 Main dashboard

Include:

- Natural-language travel request input.
- Origin and destination fields.
- Date selection.
- Traveler configuration.
- Budget and currency selection.
- Preferences and constraints.
- Clear planning and search controls.
- Progress indicators for actual planning stages.
- Error and missing-data messages.

Do not force users to choose from a hardcoded destination catalog.

## 8.2 Flight comparison

Display supported returned fields:

- Airline.
- Departure and arrival times.
- Journey duration.
- Stops.
- Price.
- Relevant airport details.
- Booking or source link when supplied.

Clearly identify unavailable information.

## 8.3 Hotel comparison

Display supported returned fields:

- Hotel name.
- Images where available.
- Rating and review count where available.
- Location.
- Amenities.
- Nightly price where supplied.
- Total stay price where supplied.
- Source or booking link where supplied.

Do not present a hotel as confirmed or available unless the provider response supports that claim.

## 8.4 Attractions

Display:

- Real attraction names.
- Categories.
- Addresses or locations.
- Source-backed information.
- Opening hours when available.
- Map coordinates when available.

## 8.5 Day-wise itinerary

For each day, show:

- Date.
- Suggested activities.
- Visit order.
- Travel duration between stops where available.
- Route information.
- Weather information where available.
- Scheduling conflicts.
- Missing information that affects feasibility.

## 8.6 Budget dashboard

Show:

- Flight costs.
- Hotel costs.
- Other verified costs.
- Known subtotal.
- Missing cost categories.
- Supported estimates.
- Budget remaining when the comparison is meaningful.

Do not make the interface appear more certain than the available data.

## 8.7 Maps

Use real coordinates and supported routing information.

Do not invent map pins, distances, or routes.

## 8.8 Source transparency

Show the provider and relevant retrieval time for important external information.

Clearly distinguish:

- Provider-returned facts.
- Calculated values.
- AI-generated explanations.
- Unknown or unavailable data.

## 8.9 Error states

Display clear messages for:

- Missing API credentials.
- Provider timeouts.
- Rate limits and quota exhaustion.
- Empty successful searches.
- Invalid search parameters.
- Unsupported forecast dates.
- Missing hotel pricing.
- Incomplete itinerary data.

A failed search must never silently produce fake results.

## 8.10 Local trip history

Implement optional trip history using browser storage.

Requirements:

- Save generated itineraries locally when the user chooses to save them.
- Allow users to reopen or delete saved trips.
- Store only the information needed to restore the locally saved itinerary.
- Preserve provider timestamps so old search results are not presented as fresh.
- Make it clear that saved search results may become stale.
- Do not automatically refresh saved results.
- Do not automatically consume API credits when reopening a saved trip.
- Do not send saved browser data to an external provider without an explicit user action.

Use `localStorage` for small records or IndexedDB if the stored data becomes too large or structured for local storage.

Do not implement user accounts, cloud synchronization, or cross-device persistence.

---

# 9. STATE MANAGEMENT WITHOUT A DATABASE

There must be no database in the initial project.

Use the following state strategy:

**React state:** Active form values, UI state, selected candidates, and currently displayed itinerary.

**Backend in-memory state:** Temporary state for a single planning operation, including structured results passed between agents.

**Browser local storage or IndexedDB:** Optional locally saved trip history and user preferences.

**External providers:** Source of truth for live travel data.

Do not rely on backend in-memory state for permanent storage. It can disappear when the server restarts.

Do not create a backend file-based database as an alternative.

If browser storage is cleared, local saved trips may be lost. Document this limitation.

If permanent cloud history or cross-device synchronization becomes a requirement, discuss it with me before adding a database in a later version.

---

# 10. SECURITY AND RELIABILITY

Implement:

- Backend-only API credentials.
- Environment-based configuration.
- A `.env.example` containing placeholders.
- A `.gitignore` that excludes `.env` and secret files.
- Input validation.
- Appropriate request and response timeouts.
- Safe error handling.
- CORS configuration for local development.
- Input size limits.
- Logging without secrets.
- Bounded agent execution.
- Strict external tool-call authorization.
- Protection against unbounded LLM tool calls.
- Per-request state isolation.

Never expose API keys or authorization headers in the frontend, logs, or API responses.

Treat external provider responses and user-supplied content as untrusted input.

Do not allow provider-returned text to override system instructions or authorize new external tool calls.

Do not add database security configuration because no database is being used.

---

# 11. ENVIRONMENT CONFIGURATION

Create a `.env.example` file containing:

`GROQ_API_KEY=`

`GROQ_MODEL=`

`SERPAPI_API_KEY=`

`GEOAPIFY_API_KEY=`

`OPENWEATHER_API_KEY=`

Add other non-secret configuration variables only when necessary.

Create a central settings module that validates configuration safely.

The application must start locally even if optional provider credentials are missing. The affected capability must return a clear configuration error when requested.

Do not test credentials by making live requests.

The actual `.env` file must remain excluded from version control.

Do not include database connection strings, database dependencies, or database credentials.

---

# 12. TESTING REQUIREMENTS

All live API testing will be performed by me manually.

Antigravity must implement local tests without making real external requests.

## 12.1 Required local tests

Implement tests for:

- TripState validation.
- Request parsing.
- Provider response parsing.
- Missing and malformed provider fields.
- Provider error handling.
- Budget calculations.
- Constraint validation.
- Itinerary scheduling.
- Candidate ranking.
- Bounded agent execution.
- Planning Coordinator behavior.
- Source provenance.
- Empty successful search results.
- Failed provider requests.
- Missing API credentials.
- No-fallback behavior.
- Prevention of fabricated production responses.
- Absence of automatic external searches.
- Browser storage serialization and restoration.
- Saved itinerary deletion.
- Correct handling of stale saved search results.

Synthetic provider-response fixtures are permitted inside isolated test code to test parsing and error handling.

These fixtures must never be imported into runtime modules or displayed as real travel results.

Do not register mock providers in the production dependency graph.

Do not claim that synthetic tests verify actual live provider behavior.

## 12.2 Local integration tests

Test frontend/backend integration without contacting external APIs.

Where necessary, inject isolated test dependencies at provider boundaries.

Ensure that test-only fixtures cannot leak into production configuration.

## 12.3 Verification before handover

Before declaring the application ready for my testing:

1. Run permitted local unit tests.
2. Run local frontend/backend integration tests.
3. Run static checks.
4. Verify that application startup makes no external requests.
5. Verify that page loading makes no external requests.
6. Verify that health checks make no external requests.
7. Verify that no automatic retries consume API quota.
8. Verify that flight and hotel adapters use the same SerpApi key configuration.
9. Verify that failed searches cannot produce fabricated travel results.
10. Verify that no hidden fallback mode exists.
11. Verify that secrets are not exposed.
12. Verify that no database dependencies or database configuration remain.
13. Document integrations whose live behavior remains unverified.

Only claim that local tests passed if they were actually executed and passed.

Never claim that live API testing passed before I have performed it.

---

# 13. RECOMMENDED PROJECT STRUCTURE

Create a clean, maintainable structure similar to the following:

agenttrip/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── features/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── providers/
│   │   │   ├── serpapi/
│   │   │   ├── geoapify/
│   │   │   └── openweather/
│   │   ├── agents/
│   │   ├── orchestration/
│   │   ├── planning/
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── docs/
│   ├── architecture.md
│   ├── api_integrations.md
│   └── manual_testing.md
├── .gitignore
└── README.md

Adapt this structure when appropriate, but preserve the separation between providers, agents, orchestration, deterministic planning, and frontend components.

Do not create empty modules simply to match the directory tree.

Do not create database, ORM, migration, or repository modules for a database that does not exist.

---

# 14. FOUR-PHASE IMPLEMENTATION PLAN

The project must be organized into exactly four major phases.

Smaller internal tasks are allowed, but do not create additional top-level phases.

Complete each phase sequentially. Do not skip ahead.

## PHASE 1: ARCHITECTURE, BACKEND AND API INTEGRATIONS

Build the entire backend foundation.

Tasks:

- Inspect the empty project folder.
- Establish the project architecture.
- Initialize FastAPI.
- Implement configuration management and environment validation.
- Define typed data models and Pydantic schemas.
- Implement error handling.
- Implement provider interfaces and adapters.
- Implement SerpApi Google Flights integration code.
- Implement SerpApi Google Hotels integration code using the same API key.
- Implement Geoapify Places integration code.
- Implement Geoapify Routing integration code.
- Implement OpenWeather integration code.
- Implement the Groq client interface.
- Implement deterministic budget calculations.
- Implement deterministic constraint validation.
- Implement provider response normalization and provenance.
- Implement local tests for parsing, configuration, and backend logic.
- Document provider parameters, expected response schemas, and manual testing requirements.

Review available official API documentation and response schemas before implementing each adapter.

**Testing restrictions:**

- Do not make real API requests.
- Do not verify API keys using live requests.
- Do not run real flight, hotel, place, route, or weather searches.
- Use local tests only.

**No-database requirement:**

Do not install or configure any database. Use typed in-memory objects for the active planning operation.

**Phase 1 completion criteria:**

- Backend foundation is implemented.
- Provider adapters are separated and typed.
- Flights and hotels use the same SerpApi key configuration.
- Errors and missing data are handled correctly.
- Local tests pass.
- No database is present.
- No external API requests have been made.

## PHASE 2: MULTI-AGENT INTELLIGENCE AND PLANNING ENGINE

Implement the complete multi-agent planning system.

Tasks:

- Implement the Travel Request Understanding Agent.
- Implement the Flight Research Agent.
- Implement the Hotel Research Agent.
- Implement the Places and Activities Agent.
- Implement the Routing and Scheduling Agent.
- Implement the Weather Agent.
- Implement the Budget and Constraint Validation Agent.
- Implement the Itinerary Synthesis Agent.
- Implement the central Planning Coordinator.

Add:

- Natural-language request parsing.
- Clarification questions.
- Structured TripState management.
- Explicit authorization for external tool calls.
- Bounded agent execution.
- Candidate comparison and ranking.
- Deterministic budget validation.
- Scheduling and feasibility validation.
- Bounded replanning.
- Source provenance and timestamp propagation.
- Structured itinerary output.
- Transparent handling of incomplete results and provider errors.

Use Groq for reasoning where appropriate, deterministic Python logic for hard constraints, and actual provider adapters as the only source of external travel facts.

Maintain active planning state in memory, with isolated state for each planning request.

**Testing restrictions:**

- Use local unit tests.
- Use synthetic fixtures only inside isolated test code.
- Never execute live searches.
- Never consume API credits.
- Never use fabricated responses as production recommendations.

**Phase 2 completion criteria:**

- All agents are implemented.
- The coordinator orchestrates the planning workflow.
- Agent execution is bounded.
- Planning and budget logic can be tested locally.
- No database is used.
- No live API calls have been made.

## PHASE 3: FRONTEND AND FULL APPLICATION INTEGRATION

Implement the complete React frontend and integrate it with the backend and planning engine.

Tasks:

- Build the natural-language trip request interface.
- Implement origin, destination, dates, travelers, budget, and preference inputs.
- Implement clarification and validation flows.
- Implement explicit user-controlled planning initiation.
- Implement actual planning progress indicators.
- Build flight comparison views.
- Build hotel comparison views.
- Build attraction discovery views.
- Build day-wise itinerary views.
- Build the budget dashboard.
- Implement map and route visualization.
- Show provider provenance and retrieval timestamps.
- Implement loading, empty-result, and error states.
- Make the interface responsive.
- Connect all relevant frontend operations to backend endpoints.
- Implement local trip saving and history through browser storage.

Ensure that:

- The frontend does not directly expose API keys.
- The frontend does not initiate searches on page load.
- The backend does not automatically search when it starts.
- Planning requests are explicitly initiated by the user.
- Errors are never replaced by fake results.
- Partial information is displayed honestly.
- Saved itineraries are local to the browser and are not represented as synchronized across devices.
- Reopening a saved itinerary does not automatically trigger a live search.

**Testing restrictions:**

- Use local frontend tests.
- Use local backend/frontend integration tests.
- Do not execute real external API calls.
- Do not run a live end-to-end trip search.

**Phase 3 completion criteria:**

- Frontend and backend run locally.
- Major user flows are integrated.
- The interface displays structured results correctly.
- Errors and missing data are handled transparently.
- Local trip history works in browser storage.
- Local integration tests pass.
- No database is used.
- No live API calls have been made.

## PHASE 4: FINAL VERIFICATION, DOCUMENTATION AND MANUAL HANDOVER

Prepare the project for manual live testing by me.

Tasks:

- Run all permitted local tests.
- Run static checks.
- Inspect the complete codebase.
- Check for fake runtime data.
- Check for fallback behavior.
- Check for hardcoded travel results.
- Check for automatic API requests.
- Check for hidden retries.
- Check for unbounded agent loops.
- Verify the shared SerpApi configuration.
- Verify secret handling.
- Verify provider error handling.
- Verify source provenance.
- Verify budget uncertainty handling.
- Verify that no database dependencies or configuration exist.
- Verify local browser storage behavior.
- Complete the README.
- Complete architecture documentation.
- Complete API integration documentation.
- Complete `.env.example`.
- Complete local installation and startup instructions.
- Complete manual testing documentation.

### Mandatory manual testing handover

Prepare individual manual tests for:

1. Starting the backend and frontend without external requests.
2. Verifying frontend/backend connectivity.
3. Performing a flight search manually.
4. Performing a hotel search manually using the same SerpApi key.
5. Verifying hotel pricing fields.
6. Testing Geoapify place discovery.
7. Testing Geoapify routing.
8. Testing OpenWeather with a supported date.
9. Generating a complete trip plan.
10. Verifying that the itinerary uses only returned candidates.
11. Verifying budget and schedule validation.
12. Testing provider errors and quota exhaustion carefully.
13. Verifying that no fake itinerary appears when required data is unavailable.
14. Saving and reopening a trip using browser storage.
15. Confirming that reopening a saved trip does not initiate external requests.

Clearly identify which tests consume live API quota.

Do not combine every provider into one expensive initial test.

### Mandatory stopping point

Once local verification and documentation are complete, stop.

Do not execute live API tests.

Do not make a real search to demonstrate that the application works.

Do not independently consume my available API credits.

I will manually execute the live tests when I choose.

**Phase 4 completion criteria:**

- All permitted local tests have been run and their results documented.
- The application is ready for manual live testing.
- Live integrations are clearly marked as unverified until I test them.
- Complete setup instructions and manual test procedures are available.
- No database is used.
- No live API calls have been made by Antigravity.

---

# 15. MANUAL TESTING AND ERROR-HANDLING POLICY

The following behavior is mandatory.

### Successful provider response

Use the actual returned data, normalize it, preserve its provenance, and pass it to the planning system.

### Successful search with zero results

Report that the search completed but returned no results. Do not fabricate alternatives.

### Missing API credentials

Return a clear configuration error for the requested capability. Do not attempt to test the key automatically.

### Invalid API credentials

When I manually initiate a request and the provider rejects the credentials, show an appropriate error without exposing secrets.

### Rate limit or quota exhaustion

Report the provider's rate-limit or quota error. Do not retry automatically.

### Timeout or provider failure

Report the failure and identify the affected capability. Do not replace the response with fake data.

### Missing fields

Preserve available information and mark unsupported or missing fields as unavailable.

### Incomplete budget

Show the known subtotal and identify missing costs. Do not claim the trip is affordable when essential costs are unknown.

### Unsupported weather date

Explain that a reliable forecast is unavailable for the requested date.

### Infeasible itinerary

Explain the specific scheduling, budget, or travel constraint that could not be satisfied. Suggest alternatives only when supported by available information.

### Saved trip history

Use browser storage. Make it clear that saved search results can become stale and that reopening them does not refresh the data.

---

# 16. DOCUMENTATION REQUIREMENTS

The README must explain:

- What AgentTrip does.
- The architecture.
- The technology stack.
- Required API keys.
- How to configure the environment.
- How to install backend dependencies.
- How to install frontend dependencies.
- How to start the backend.
- How to start the frontend.
- How to use the application.
- How the agents coordinate.
- How budget validation works.
- What data each provider supplies.
- How source provenance is handled.
- Known provider limitations.
- How to run local tests.
- Which tests require manual live API requests.
- How local trip history works.
- The limitations of browser storage.
- The fact that no database is used.

The API integration documentation must explain provider-specific parameters, expected response fields, normalization logic, error handling, and limitations.

The manual testing documentation must identify each real API operation and make it clear when it consumes search quota.

Never claim that a live integration has been verified if it has not been manually tested.

---

# 17. FINAL ACCEPTANCE CRITERIA

AgentTrip is ready for manual testing when all the following are true:

- The application is implemented from scratch.
- The frontend and backend run locally.
- The project follows the four-phase implementation plan.
- The system implements genuine multi-agent planning.
- Groq powers the appropriate reasoning tasks.
- SerpApi supplies both flights and hotels through the same API key.
- Geoapify supplies supported place and routing data.
- OpenWeather supplies supported weather information.
- External facts retain their provenance.
- Budget calculations use deterministic logic.
- Missing information is represented honestly.
- No fabricated travel facts can enter production responses.
- No fallback provider or demo mode exists.
- External searches require explicit user-controlled planning actions.
- Application startup and health checks do not call external providers.
- Local tests do not consume external API quotas.
- Agent execution and tool calls are bounded.
- Secrets remain on the backend.
- Provider errors are handled transparently.
- No database or database dependency is present.
- Active planning state is maintained in memory.
- Local trip history works using browser storage.
- Cross-device synchronization is not falsely promised.
- Local test results are documented.
- The application is ready for me to perform live API testing manually.

Do not mark the project fully live-verified until I have completed those tests.

---

# 18. YOUR FIRST ACTION — BEGIN PHASE 1

Start with Phase 1 only.

First:

1. Inspect the new, empty project folder.
2. Review the architecture and establish the core design.
3. Review available official API documentation and response schemas.
4. Identify provider-specific limitations and important implementation decisions.
5. Define the typed data models and provider interfaces.
6. Confirm how live-only operation, explicit search authorization, and the no-automatic-testing rule will be enforced.
7. Confirm that the project will not use a database.
8. Present the concise Phase 1 implementation plan.

Then implement Phase 1.

Do not generate the entire application in one uncontrolled step. Do not skip phases. Complete each phase's acceptance criteria before proceeding to the next phase.

Do not make external API calls.

Do not test API keys.

Do not consume API search credits.

Do not add fake runtime data or fallback modes.

Do not install or configure a database.

Maintain the exact four-phase project structure throughout development.

The priority is to build a clean, reliable, maintainable, genuinely agentic travel planner that uses real-world data and keeps all live API testing under my control.
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-10-10T14:23:13+05:30.
</ADDITIONAL_METADATA>
<USER_SETTINGS_CHANGE>
The user changed setting `Model Selection` from None to Claude Sonnet 5.5 (Medium). No need to comment on this change if the user doesn't ask about it. If reporting what model you are, please use a human readable name instead of the exact string.
</USER_SETTINGS_CHANGE>