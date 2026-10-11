# Manual Testing Checklist

This checklist is designed to verify live API integrations step-by-step, minimizing unnecessary API quota consumption. 
**Do not automate these tests.** 

### Preparation
1. **Local Setup:** Start the backend (`uvicorn app.main:app --reload` in `backend/`) and frontend (`npm run dev` in `frontend/`) without making external requests.
2. **Connectivity:** Open the frontend in the browser and verify the UI loads. Ensure the `.env` file is populated with valid API keys.

### Provider Verification (In Order)
3. **SerpApi Flights:** 
   - Manually invoke the `/api/plan` endpoint or a test script pointing *only* at the `SerpApiFlightsAdapter` using a known route (e.g., NYC to LON next week). Verify the structure of the returned `FlightOption` items.
4. **SerpApi Hotels:**
   - Using the same SerpApi key, invoke the `SerpApiHotelsAdapter` for a 1-night stay in London. Verify price parsing.
5. **Geoapify Places:**
   - Invoke the `GeoapifyPlacesAdapter` for attractions in London. Verify categories and returned `PlaceOption` items.
6. **Geoapify Routing:**
   - Invoke the `GeoapifyRoutingAdapter` for two known coordinates in London. Verify transit/walking times.
7. **OpenWeather:**
   - Invoke the `OpenWeatherAdapter` for London. Use a date within 5 days for forecast capability. Verify it returns `WeatherForecast`.
8. **Groq LLM Structured Output:**
   - Test the `ItinerarySynthesisAgent.synthesize` with mock context. Ensure it properly outputs JSON matching `LLMSynthesisOutput` without hallucinations.

### End-to-End Run
9. **Full Planning Run:**
   - In the frontend UI, enter a complete, unambiguous prompt (e.g., *"I want to go from New York to London next week for 5 days. Budget is $5000 total. 2 adults."*)
   - Monitor the SSE events.
   - Wait for terminal completion.
10. **Result Inspection:**
    - Inspect the rendered itinerary.
    - Check the system status pill badges (ensure they display success or expected capabilities).
    - Review the budget breakdown (verify no invented prices).
    - Ensure missing information (e.g., exact transit times if routing failed) is correctly reported rather than fabricated.
