# Provider integrations

> **Verification status: NONE of these integrations has been verified live.** They were implemented
> from official documentation and tested only against synthetic payloads in isolated tests.
> Update this status only after you have run the manual tests in `manual_testing.md`.

Sources: SerpApi Google Flights / Google Hotels API docs, Geoapify Places/Routing/Geocoding docs,
OpenWeather 2.5 docs, Groq OpenAI-compatible API docs.

## SerpApi Google Flights — `SerpApiFlightsAdapter` (`GET https://serpapi.com/search.json`)
Credential: `SERPAPI_API_KEY` (shared with hotels). **Each search consumes SerpApi quota.**

| Our field | SerpApi param |
|---|---|
| origin / destination | `departure_id` / `arrival_id` (IATA or kgmid) |
| outbound / return date | `outbound_date`, `return_date`; `type` = 1 round trip, 2 one way |
| adults/children/infants | `adults`, `children`, `infants_in_seat`, `infants_on_lap` |
| travel_class | `travel_class` 1–4 |
| max_stops | `stops`: 0→1 (nonstop), 1→2, 2→3 |
| max_duration_minutes | `max_duration` |
| include/exclude airlines | `include_airlines` / `exclude_airlines` |
| currency, gl, hl | `currency`, `gl`, `hl` |
| departure_token | `departure_token` (return leg of a chosen outbound flight; a separate paid search) |

Response used: `best_flights[]`, `other_flights[]` → `flights[]` (airports, times, duration, airline,
flight_number, airplane, travel_class, overnight, legroom, extensions), `layovers[]`, `total_duration`,
`price`, `type`, `carbon_emissions.this_flight`, `departure_token`, `booking_token`;
`search_metadata.id/google_flights_url`; `price_insights` (kept as provider extras).

Normalization: stops = `len(flights)-1`; times parsed as naive local `YYYY-MM-DD HH:MM`
(unparseable → `None`); `price` → `Money` in the response (or requested) currency; missing price stays
`None`. Malformed entries are skipped with a warning. **No results** (SerpApi's "hasn't returned any
results" error) → `status="empty"`. Other `error` bodies → `ProviderRequestError`.

Limitations: provider does not state if the price is per traveler or total (`price_scope`
= `unspecified_by_provider`); round-trip results describe the outbound leg only; fares are not guaranteed.

## SerpApi Google Hotels — `SerpApiHotelsAdapter` (same endpoint, `engine=google_hotels`)
Same `SERPAPI_API_KEY`; **each search consumes quota**.

Params: `q`, `check_in_date`, `check_out_date`, `adults`, `children` + `children_ages` (1–17, count must
match), `currency`, `gl`, `hl`, `sort_by` (3 price / 8 rating / 13 reviews), `min_price`, `max_price`,
`rating` (7=3.5+, 8=4.0+, 9=4.5+), `hotel_class`, `property_types`, `amenities`, `free_cancellation`,
`next_page_token` (pagination is never automatic). **There is no room-count parameter**, so none is sent.

Response used: `properties[]` → `name`, `type`, `property_token`, `link`, `gps_coordinates`,
`check_in_time/check_out_time`, `rate_per_night{lowest, extracted_lowest, before_taxes_fees…}`,
`total_rate{…}`, `prices[]` (per booking source), `images[]`, `overall_rating`, `reviews`,
`location_rating`, `extracted_hotel_class`, `amenities`, `excluded_amenities`; `serpapi_pagination.next_page_token`.
Sponsored `ads` are ignored.

Price rules: `rate_per_night` and `total_rate` are copied exactly as returned; neither is computed from the
other in the adapter. If only display text exists (e.g. `"₹2,000"` with no `extracted_*`), `amount` stays
`None`. The budget module may *calculate* nightly × nights only when it labels the result `calculated`.
Address is not in list results (always listed in `missing_fields`); cancellation terms are not included.

## Geoapify Places / Geocoding — `GeoapifyPlacesAdapter` (`GEOAPIFY_API_KEY`)
* Places: `GET /v2/places` with `categories`, `filter=circle:lon,lat,radius`, `bias=proximity:lon,lat`, `limit`.
* Geocoding: `GET /v1/geocode/search` with `text`, `limit`, `format=json` (turns a destination into coordinates).
Fields: `name`, `place_id`, `formatted`, `city`, `lat/lon`, `categories`, `distance`, `opening_hours`
(top level or `datasource.raw`), `website`, `phone`. Entrance fees, ratings and descriptions are **not** provided
and never invented. Features without coordinates are skipped.

## Geoapify Routing — `GeoapifyRoutingAdapter`
`GET /v1/routing` with `waypoints=lat,lon|lat,lon`, `mode`, `units=metric`. Uses `properties.distance` (m),
`properties.time` (s), `legs[]`, and `geometry` (LineString/MultiLineString as `[lon, lat]`).
No route → `empty`. Transit modes depend on provider coverage.

## OpenWeather — `OpenWeatherAdapter` (`OPENWEATHER_API_KEY`)
* Current: `GET /data/2.5/weather`. Forecast: `GET /data/2.5/forecast` (5 days, 3-hour blocks), `units=metric`.
* Current weather and forecast are separate methods/types. `planning/weather_coverage.assess_dates` states per date
  whether the forecast is `available`, `partial`, `unavailable_beyond_horizon`, `unavailable_before_window` or
  `unavailable_no_data` (using the city's timezone offset). Beyond-horizon dates are **never** filled.
* Each call consumes OpenWeather quota (current and forecast are 2 separate calls).

## Groq — `GroqLLMClient` (`GROQ_API_KEY`, `GROQ_MODEL`)
`POST https://api.groq.com/openai/v1/chat/completions` (Bearer auth). The model is **configuration only**; choose a
current model that supports tool calling/JSON output from <https://console.groq.com/docs/models>
(for example the `openai/gpt-oss-*` or `llama-3.3-70b-versatile` families listed there at the time of writing).
`complete_structured` uses JSON mode + Pydantic validation; invalid output raises `LLMOutputError` (never retried).
Tool calls returned by the model are *requests* only: the client never executes them. Groq calls count toward
the per-run `llm` limit and consume Groq quota.

## Error mapping (all providers)
| Condition | Exception (`code`) | Notes |
|---|---|---|
| credential missing | `MissingCredentialsError` (`missing_credentials`) | before any request, no quota used |
| 401 / 403 | `ProviderAuthError` | message redacted |
| 429 | `ProviderRateLimitError` | never retried |
| timeout | `ProviderTimeoutError` | never retried |
| network / 5xx | `ProviderUnavailableError` | URL/key never included |
| other 4xx or SerpApi `error` | `ProviderRequestError` | invalid search parameters |
| non-JSON / unexpected shape | `ProviderResponseError` | |
| zero results | **success** with `status="empty"` | not an error |
| call budget / duplicate / closed run | `ToolCallLimitExceeded` / `DuplicateSearchError` / `ToolAuthorizationError` | |

API error JSON: `{"error": {"code", "message", "provider", "capability", "retry": "manual_only", "details"}}`.
