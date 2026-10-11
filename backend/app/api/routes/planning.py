import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.budget import BudgetAndConstraintValidationAgent
from app.agents.coordinator import PlanningCoordinator
from app.agents.flight import FlightResearchAgent
from app.agents.hotel import HotelResearchAgent
from app.agents.places import PlacesAndActivitiesAgent
from app.agents.routing import RoutingAndSchedulingAgent
from app.agents.synthesis import ItinerarySynthesisAgent
from app.agents.understanding import TravelRequestUnderstandingAgent
from app.agents.weather import WeatherAgent
from app.api.deps import get_coordinator
from app.core.authorization import SearchAuthorizer
from app.core.config import get_settings
from app.models.common import Capability
from app.models.itinerary import (
    DayPlan,
    ProviderResultStatus,
    ProviderStatus,
    StructuredItinerary,
)

router = APIRouter(tags=["planning"])

class PlanRequest(BaseModel):
    request: str
    existing_state: str | None = None

class SessionState:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.completed = False
        self.result = None

sessions: dict[str, SessionState] = {}


def summarize_flight_item(item: Any) -> dict[str, Any]:
    """Extract core flight constraints to keep synthesis token footprint lean."""
    if isinstance(item, dict):
        return {k: v for k, v in item.items() if k in {"airline", "price", "stops", "total_duration_minutes", "flight_numbers"}}
    flight_nums = []
    first_dep = None
    last_arr = None
    segments = getattr(item, "segments", []) or []
    for s in segments:
        fn = getattr(s, "flight_number", None)
        if fn:
            flight_nums.append(fn)
        dep_apt = getattr(s, "departure", None)
        arr_apt = getattr(s, "arrival", None)
        dep_code = getattr(dep_apt, "code", None) or getattr(dep_apt, "id", None) if dep_apt else None
        arr_code = getattr(arr_apt, "code", None) or getattr(arr_apt, "id", None) if arr_apt else None
        dep_t = getattr(dep_apt, "local_time", None) or getattr(s, "departure_time", None) if dep_apt else None
        arr_t = getattr(arr_apt, "local_time", None) or getattr(s, "arrival_time", None) if arr_apt else None
        if first_dep is None and (dep_code or dep_t):
            first_dep = f"{dep_code or ''} at {dep_t or ''}".strip()
        if arr_code or arr_t:
            last_arr = f"{arr_code or ''} at {arr_t or ''}".strip()

    price_str = None
    p = getattr(item, "price", None)
    if p and getattr(p, "amount", None) is not None:
        price_str = f"{getattr(p, 'currency', '')} {getattr(p, 'amount', '')}".strip()

    airline = getattr(item, "airline", None) or (segments[0].airline if segments else None)

    return {
        "airline": airline,
        "flight_numbers": flight_nums,
        "departure": first_dep,
        "arrival": last_arr,
        "stops": getattr(item, "stops", 0),
        "duration_min": getattr(item, "total_duration_minutes", None),
        "price": price_str,
        "trip_type": getattr(item, "trip_type", None),
        "return_leg_pending": getattr(item, "return_leg_details_pending", False),
    }


def summarize_hotel_item(item: Any) -> dict[str, Any]:
    """Extract core hotel constraints to keep synthesis token footprint lean."""
    if isinstance(item, dict):
        return {k: v for k, v in item.items() if k in {"name", "hotel_class", "rating", "nightly_rate", "total_rate"}}
    nightly_str = None
    nr = getattr(item, "nightly_rate", None)
    if nr:
        if getattr(nr, "amount", None) and getattr(nr.amount, "amount", None) is not None:
            nightly_str = f"{getattr(nr.amount, 'currency', '')} {getattr(nr.amount, 'amount', '')}".strip()
        elif getattr(nr, "display_text", None):
            nightly_str = nr.display_text

    total_str = None
    tr = getattr(item, "total_rate", None)
    if tr:
        if getattr(tr, "amount", None) and getattr(tr.amount, "amount", None) is not None:
            total_str = f"{getattr(tr.amount, 'currency', '')} {getattr(tr.amount, 'amount', '')}".strip()
        elif getattr(tr, "display_text", None):
            total_str = tr.display_text

    amenities = getattr(item, "amenities", []) or []
    return {
        "name": getattr(item, "name", None),
        "stars": getattr(item, "hotel_class", None),
        "rating": getattr(item, "rating", None),
        "nightly_rate": nightly_str,
        "total_rate": total_str,
        "amenities": amenities[:5],
    }


def summarize_place_item(item: Any) -> dict[str, Any]:
    """Extract core place/attraction constraints to keep synthesis token footprint lean."""
    if isinstance(item, dict):
        return {k: v for k, v in item.items() if k in {"name", "categories", "address", "rating", "opening_hours"}}
    categories = getattr(item, "categories", []) or []
    summary: dict[str, Any] = {
        "name": getattr(item, "name", None),
        "categories": categories[:3],
        "address": getattr(item, "address", None) or getattr(item, "city", None),
    }
    rating = getattr(item, "rating", None)
    if rating is not None:
        summary["rating"] = rating
    hours = getattr(item, "opening_hours", None)
    if hours:
        summary["opening_hours"] = hours
    return summary


async def run_planning_workflow(session_id: str, request_text: str, existing_state: str | None, coordinator: PlanningCoordinator):
    session = sessions[session_id]
    
    async def emit(stage: str, message: str, data: dict | None = None):
        event = {"stage": stage, "message": message, "data": data}
        await session.queue.put(event)
        
    try:
        settings = get_settings()
        authorizer = SearchAuthorizer(
            run_id=session_id, 
            limits=settings.call_limits()
        )
        
        # Track provider responses for structured output
        provider_data: dict[str, list[Any]] = {
            "flights": [],
            "hotels": [],
            "places": [],
        }
        provider_statuses: dict[str, ProviderResultStatus] = {}
        
        from app.providers.gemini.client import GeminiUnderstandingClient
        # 1. Understanding
        await emit("understanding", "Analyzing your request...")
        understanding_agent = TravelRequestUnderstandingAgent(coordinator.understanding_llm)
        
        # We need a way to track the conversation state if we want follow-ups.
        # But for now, we just pass request_text.
        try:
            trip_state = await understanding_agent.understand(request_text, date.today(), authorizer, existing_state=existing_state)
        except Exception as e:
            await emit("error", f"Understanding failed: {e!s}")
            return
            
        await emit("understanding", "Trip details understood.", {"trip_state": trip_state.model_dump(mode='json')})
        
        # Check clarification question from Gemini
        if trip_state.clarification_question:
            await emit("clarification_needed", trip_state.clarification_question, {"trip_state": trip_state.model_dump(mode='json')})
            return
            
        contradictions = trip_state.contradictions(date.today())
        if contradictions:
            await emit("clarification_needed", "Found contradictory information.", {"contradictions": contradictions})
            return
            
        from app.models.geo import GeocodeRequest
        dest_coords = None
        if trip_state.destination:
            try:
                geocode_req = GeocodeRequest(text=trip_state.destination)
                geocode_res = await coordinator.places.geocode(geocode_req, authorizer)
                if geocode_res.items:
                    dest_coords = geocode_res.items[0].coordinate
            except Exception:
                pass

            
        async def tool_executor(call) -> str:
            res_str, actual_model, status = await coordinator.execute_tool(call, authorizer)
            if status.status != ProviderStatus.ERROR:
                if status.capability == Capability.FLIGHTS and actual_model and hasattr(actual_model, "items"):
                    provider_data["flights"].extend(actual_model.items)
                elif status.capability == Capability.HOTELS and actual_model and hasattr(actual_model, "items"):
                    provider_data["hotels"].extend(actual_model.items)
                elif status.capability == Capability.PLACES and actual_model and hasattr(actual_model, "items"):
                    provider_data["places"].extend(actual_model.items)
            # Record status (preserve SUCCESS if earlier call succeeded and items were obtained)
            prev_status = provider_statuses.get(status.capability.value)
            if (
                prev_status
                and prev_status.status == ProviderStatus.SUCCESS
                and status.status != ProviderStatus.SUCCESS
                and provider_data.get(status.capability.value)
            ):
                pass
            else:
                provider_statuses[status.capability.value] = status
            return res_str
            
        # 2. Flight Research
        await emit("flight_research", "Searching for flights...")
        flight_context = trip_state.model_dump_json(include={"origin", "destination", "departure_date", "return_date", "travelers", "preferences", "hard_constraints"})
        flight_agent = FlightResearchAgent(coordinator.llm)
        try:
            flight_summary = await flight_agent.run(f"Find flights for the trip. Context: {flight_context}", authorizer, tool_executor)
        except Exception as e:  # noqa: BLE001
            flight_summary = f"Flight research failed: {e!s}"
            provider_statuses[Capability.FLIGHTS.value] = ProviderResultStatus(capability=Capability.FLIGHTS, status=ProviderStatus.ERROR, error_detail=str(e))
        if Capability.FLIGHTS.value not in provider_statuses:
            provider_statuses[Capability.FLIGHTS.value] = ProviderResultStatus(capability=Capability.FLIGHTS, status=ProviderStatus.NOT_REQUESTED)
        await emit("flight_research", "Flights evaluated")
        
        # 3. Hotel Research
        await emit("hotel_research", "Searching for hotels...")
        hotel_context = trip_state.model_dump_json(include={"destination", "departure_date", "return_date", "travelers", "rooms", "preferences", "hard_constraints"})
        hotel_agent = HotelResearchAgent(coordinator.llm)
        try:
            hotel_summary = await hotel_agent.run(f"Find hotels for the trip. Context: {hotel_context}", authorizer, tool_executor)
        except Exception as e:  # noqa: BLE001
            hotel_summary = f"Hotel research failed: {e!s}"
            provider_statuses[Capability.HOTELS.value] = ProviderResultStatus(capability=Capability.HOTELS, status=ProviderStatus.ERROR, error_detail=str(e))
        if Capability.HOTELS.value not in provider_statuses:
            provider_statuses[Capability.HOTELS.value] = ProviderResultStatus(capability=Capability.HOTELS, status=ProviderStatus.NOT_REQUESTED)
        await emit("hotel_research", "Hotels evaluated")
        
        # 4. Attractions
        await emit("attractions", "Discovering attractions...")
        places_ctx = trip_state.model_dump(mode="json", include={"destination", "departure_date", "return_date", "preferences"})
        if dest_coords:
            places_ctx["destination_coordinates"] = dest_coords.model_dump()
        places_context = json.dumps(places_ctx)
        places_agent = PlacesAndActivitiesAgent(coordinator.llm)
        places_prompt = (
            f"Find attractions and points of interest for the destination. "
            f"In your first search, batch the most useful attraction categories together in a single call "
            f"(e.g. categories=['tourism.sights', 'tourism.attraction', 'heritage', 'leisure.park', 'entertainment.culture']). "
            f"Context: {places_context}"
        )
        try:
            places_summary = await places_agent.run(places_prompt, authorizer, tool_executor)
        except Exception as e:  # noqa: BLE001
            places_summary = f"Attractions research failed: {e!s}"
            if not provider_data.get("places"):
                provider_statuses[Capability.PLACES.value] = ProviderResultStatus(capability=Capability.PLACES, status=ProviderStatus.ERROR, error_detail=str(e))
        if Capability.PLACES.value not in provider_statuses:
            provider_statuses[Capability.PLACES.value] = ProviderResultStatus(
                capability=Capability.PLACES,
                status=ProviderStatus.SUCCESS if provider_data.get("places") else ProviderStatus.NOT_REQUESTED,
            )
        await emit("attractions", "Attractions discovered")
        
        # 5. Routing
        await emit("routing", "Evaluating routes...")
        routing_ctx = trip_state.model_dump(mode="json", include={"destination", "preferences"})
        if dest_coords:
            routing_ctx["destination_coordinates"] = dest_coords.model_dump()
        routing_ctx["places"] = [p.model_dump(mode="json", exclude={"provenance", "images"}) for p in provider_data.get("places", [])[:5]]
        routing_context = json.dumps(routing_ctx)
        routing_agent = RoutingAndSchedulingAgent(coordinator.llm)
        try:
            routing_summary = await routing_agent.run(f"Estimate routes between key places. Context: {routing_context}", authorizer, tool_executor)
        except Exception as e:  # noqa: BLE001
            routing_summary = f"Routing evaluation failed: {e!s}"
            provider_statuses[Capability.ROUTING.value] = ProviderResultStatus(capability=Capability.ROUTING, status=ProviderStatus.ERROR, error_detail=str(e))
        if Capability.ROUTING.value not in provider_statuses:
            provider_statuses[Capability.ROUTING.value] = ProviderResultStatus(capability=Capability.ROUTING, status=ProviderStatus.NOT_REQUESTED)
        await emit("routing", "Routes evaluated")
        
        # 6. Weather
        await emit("weather", "Checking weather...")
        weather_ctx = trip_state.model_dump(mode="json", include={"destination", "departure_date", "return_date"})
        if dest_coords:
            weather_ctx["destination_coordinates"] = dest_coords.model_dump()
        weather_context = json.dumps(weather_ctx)
        
        days_ahead = (trip_state.departure_date - date.today()).days if trip_state.departure_date else 0
        if days_ahead > 5:
            weather_summary = f"Weather forecast is unavailable for dates more than 5 days in the future (requested: {trip_state.departure_date})."
            provider_statuses[Capability.WEATHER.value] = ProviderResultStatus(
                capability=Capability.WEATHER, 
                status=ProviderStatus.UNAVAILABLE, 
                error_detail="Dates exceed the 5-day forecast horizon."
            )
        else:
            weather_kind = "current" if trip_state.departure_date == date.today() else "forecast"
            weather_agent = WeatherAgent(coordinator.llm)
            try:
                weather_summary = await weather_agent.run(
                    f"Check the weather for the trip dates using get_weather (kind='{weather_kind}'). Context: {weather_context}",
                    authorizer,
                    tool_executor,
                )
            except Exception as e:  # noqa: BLE001
                weather_summary = f"Weather check failed: {e!s}"
                provider_statuses[Capability.WEATHER.value] = ProviderResultStatus(capability=Capability.WEATHER, status=ProviderStatus.ERROR, error_detail=str(e))
            if Capability.WEATHER.value not in provider_statuses:
                provider_statuses[Capability.WEATHER.value] = ProviderResultStatus(capability=Capability.WEATHER, status=ProviderStatus.NOT_REQUESTED)
            
        await emit("weather", "Weather checked")
        
        # 7. Budget & Constraint Validation
        await emit("budget", "Validating budget and constraints...")
        budget_agent = BudgetAndConstraintValidationAgent()
        sel_flight = provider_data["flights"][0] if provider_data["flights"] else None
        sel_hotel = provider_data["hotels"][0] if provider_data["hotels"] else None
        
        b, _f, _h = budget_agent.evaluate(trip_state, sel_flight, sel_hotel)
        await emit("budget", "Budget validated")
        
        # 8. Synthesis
        await emit("synthesis", "Preparing final itinerary...")
        synthesis_agent = ItinerarySynthesisAgent(coordinator.synthesis_llm)
        
        s_flights = json.dumps([summarize_flight_item(f) for f in provider_data.get("flights", [])[:3]])
        s_hotels = json.dumps([summarize_hotel_item(h) for h in provider_data.get("hotels", [])[:3]])
        s_places = json.dumps([summarize_place_item(p) for p in provider_data.get("places", [])[:5]])
        
        dep_date = trip_state.departure_date
        ret_date = trip_state.return_date or dep_date
        calendar_days = trip_state.calendar_days or (1 if not dep_date else (ret_date - dep_date).days + 1)

        places_available = bool(provider_data.get("places")) and (
            provider_statuses.get(Capability.PLACES.value) is None
            or provider_statuses[Capability.PLACES.value].status == ProviderStatus.SUCCESS
        )

        trip_dates_info = (
            f"Trip: from {trip_state.origin or 'Origin'} to {trip_state.destination or 'Destination'}. "
            f"Departure Date: {dep_date}. Return Date: {ret_date}. "
            f"Total Duration: {calendar_days} calendar day(s). "
        )
        if not places_available:
            trip_dates_info += (
                "IMPORTANT: Places/attractions search returned no results from the provider. "
                "Do NOT invent attractions or activities. Clearly state in the trip summary and day plans that attraction data was unavailable. "
            )

        context = (
            f"{trip_dates_info}"
            f"Flights: {s_flights}. Hotels: {s_hotels}. Places: {s_places}. "
            f"Routing: {routing_summary}. Weather: {weather_summary}."
        )

        synthesis_error_occurred = False
        try:
            llm_out = await synthesis_agent.synthesize(context, authorizer)
            trip_summary = llm_out.trip_summary
            day_wise = llm_out.day_wise
            val_warnings = llm_out.validation_warnings
        except Exception as e:  # noqa: BLE001
            synthesis_error_occurred = True
            trip_summary = f"Partial itinerary due to synthesis error: {e!s}"
            day_wise = []
            val_warnings = [f"Synthesis failed: {e!s}"]

        # Ensure every requested travel day is included in day_wise
        if dep_date:
            expected_dates = []
            curr = dep_date
            while curr <= ret_date:
                expected_dates.append(curr)
                curr += timedelta(days=1)

            existing_by_date = {dp.date: dp for dp in day_wise if dp.date}
            for i, dp in enumerate(day_wise):
                if dp.date is None and i < len(expected_dates):
                    dp.date = expected_dates[i]
                    existing_by_date[dp.date] = dp

            completed_day_wise = []
            for i, d in enumerate(expected_dates):
                day_num = i + 1
                if d in existing_by_date:
                    completed_day_wise.append(existing_by_date[d])
                else:
                    if d == dep_date:
                        title = f"Day {day_num}: Departure & Arrival in {trip_state.destination or 'Destination'}"
                    elif d == ret_date:
                        title = f"Day {day_num}: Return Journey to {trip_state.origin or 'Origin'}"
                    else:
                        title = f"Day {day_num}: Exploring {trip_state.destination or 'Destination'}"
                    missing_notes = []
                    if synthesis_error_occurred:
                        missing_notes.append("Itinerary synthesis unavailable: detailed activities could not be scheduled.")
                    completed_day_wise.append(DayPlan(date=d, title=title, activities=[], missing_information=missing_notes))

            day_wise = completed_day_wise

        # When Places results are unavailable, return clear partial itinerary and actionable status
        if not places_available:
            if "partial" not in trip_summary.lower():
                trip_summary = (
                    f"Partial itinerary: Attractions and activity recommendations are unavailable because no places were returned by the provider. "
                    f"Verified flights and accommodation options are included below. {trip_summary}"
                )
            for dp in day_wise:
                if not dp.activities:
                    note = "Attractions and activity data unavailable from provider."
                    if note not in dp.missing_information:
                        dp.missing_information.append(note)
            places_warning = "Attractions data unavailable from provider: activities could not be scheduled. You may retry search or broaden the location."
            if places_warning not in val_warnings:
                val_warnings.append(places_warning)
            if Capability.PLACES.value not in provider_statuses or provider_statuses[Capability.PLACES.value].status not in (ProviderStatus.ERROR, ProviderStatus.UNAVAILABLE):
                provider_statuses[Capability.PLACES.value] = ProviderResultStatus(
                    capability=Capability.PLACES,
                    status=ProviderStatus.EMPTY,
                    error_detail="No attractions returned by provider."
                )

        # Create StructuredItinerary
        itinerary = StructuredItinerary(
            trip_summary=trip_summary,
            flights=provider_data["flights"],
            hotels=provider_data["hotels"],
            day_wise=day_wise,
            budget_report=b.model_dump(mode='json'),
            provider_statuses=provider_statuses,
            validation_warnings=val_warnings
        )
        
        await emit("completed", "Planning complete.", {"itinerary": itinerary.model_dump(mode='json')})
        
    except Exception as e:  # noqa: BLE001
        await emit("error", f"An error occurred: {e!s}")
    finally:
        session.completed = True
        await session.queue.put(None)

@router.post("/plan")
async def start_planning(req: PlanRequest, background_tasks: BackgroundTasks, coordinator: PlanningCoordinator = Depends(get_coordinator)):  # noqa: B008
    session_id = str(uuid.uuid4())
    sessions[session_id] = SessionState()
    background_tasks.add_task(run_planning_workflow, session_id, req.request, req.existing_state, coordinator)
    return {"session_id": session_id}

@router.get("/plan/{session_id}/stream")
async def stream_planning(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions[session_id]
    
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            event = await session.queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
