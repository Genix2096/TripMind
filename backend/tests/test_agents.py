from datetime import date
from typing import Any

import pytest

from app.agents.budget import BudgetAndConstraintValidationAgent
from app.agents.coordinator import PlanningCoordinator
from app.agents.flight import FlightResearchAgent
from app.agents.understanding import TravelRequestUnderstandingAgent
from app.core.authorization import SearchAuthorizer
from app.models.common import Capability
from app.models.trip import TripState
from app.providers.groq.client import LLMResponse, ToolCallRequest


class MockLLMClient:
    def __init__(self, expected_structured=None, expected_chat=None):
        self.expected_structured = expected_structured
        self.expected_chat = expected_chat

    async def complete_structured(self, messages: list[dict[str, Any]], schema: type, authorizer: SearchAuthorizer, **kwargs) -> Any:
        return self.expected_structured

    async def chat(self, messages: list[dict[str, Any]], authorizer: SearchAuthorizer, tools: list[dict[str, Any]] | None = None, **kwargs) -> LLMResponse:
        return self.expected_chat

@pytest.fixture
def mock_authorizer():
    return SearchAuthorizer(run_id="test", limits={Capability.FLIGHTS: 1, Capability.HOTELS: 1, Capability.PLACES: 1, Capability.ROUTING: 1, Capability.WEATHER: 1})

@pytest.mark.asyncio
async def test_understanding_agent(mock_authorizer):
    trip_state = TripState(
        origin="NYC",
        destination="LON",
        departure_date=date(2025, 1, 1),
    )
    llm = MockLLMClient(expected_structured=trip_state)
    agent = TravelRequestUnderstandingAgent(llm)
    
    result = await agent.understand("I want to go to London from NYC on 2025-01-01", date(2025, 1, 1), mock_authorizer)
    assert result.origin == "NYC"
    assert result.destination == "LON"
    assert result.raw_request == "I want to go to London from NYC on 2025-01-01"

@pytest.mark.asyncio
async def test_flight_agent_tool_call(mock_authorizer):
    expected_chat_1 = LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(id="call_1", name="search_flights", arguments={"origin": "NYC", "destination": "LON", "outbound_date": "2025-01-01", "currency": "USD"})],
        finish_reason="tool_calls",
        prompt_tokens=10,
        completion_tokens=10
    )
    expected_chat_2 = LLMResponse(
        content="Here are your flights.",
        tool_calls=[],
        finish_reason="stop",
        prompt_tokens=20,
        completion_tokens=10
    )
    
    class MultiResponseMock:
        def __init__(self, responses):
            self.responses = responses
            self.idx = 0
            
        async def chat(self, messages, authorizer, tools=None, **kwargs):
            res = self.responses[self.idx]
            self.idx += 1
            return res

    llm = MultiResponseMock([expected_chat_1, expected_chat_2])
    agent = FlightResearchAgent(llm)
    
    executed_tools = []
    
    async def mock_executor(call: ToolCallRequest):
        executed_tools.append(call.name)
        return "mock flight data"
        
    result = await agent.run("Find flights", mock_authorizer, mock_executor)
    
    assert "search_flights" in executed_tools
    assert result == "mock flight data"

@pytest.mark.asyncio
async def test_budget_agent():
    agent = BudgetAndConstraintValidationAgent()
    trip_state = TripState(
        origin="NYC", destination="LON", departure_date=date(2025, 1, 1)
    )
    b, f, h = agent.evaluate(trip_state, None, None)
    
    assert b.status.value == "no_budget_provided"
    assert f.passes
    assert h.passes

@pytest.mark.asyncio
async def test_coordinator_tool_execution(mock_authorizer):
    llm = MockLLMClient()
    # Create fake adapters
    class MockAdapter:
        pass
        
    coordinator = PlanningCoordinator(
        llm=llm,
        flights_adapter=MockAdapter(),
        hotels_adapter=MockAdapter(),
        places_adapter=MockAdapter(),
        routing_adapter=MockAdapter(),
        weather_adapter=MockAdapter(),
    )
    
    # Test error handling for unknown tool
    call = ToolCallRequest(id="1", name="unknown_tool", arguments={})
    res, _, _ = await coordinator.execute_tool(call, mock_authorizer)
    assert "Error: Unknown tool" in res
    
    # Test error handling when adapter fails (adapter is missing methods)
    call2 = ToolCallRequest(id="2", name="search_flights", arguments={"origin": "NYC", "destination": "LON", "outbound_date": "2025-01-01", "currency": "USD"})
    res2, _, _ = await coordinator.execute_tool(call2, mock_authorizer)
    assert "Error executing" in res2


@pytest.mark.asyncio
async def test_weather_tool_schema_and_execution_without_missing_kind(mock_authorizer):
    from unittest.mock import AsyncMock
    from app.agents.weather import WeatherAgent, WeatherRequest
    from app.models.common import Coordinate, Provenance
    from app.models.weather import CurrentWeather, WeatherForecast
    from datetime import datetime, UTC

    # 1. Verify exposed tool schema
    agent = WeatherAgent(MockLLMClient())
    tools = agent.tools
    assert len(tools) == 1
    tool_fn = tools[0]["function"]
    assert tool_fn["name"] == "get_weather"
    params = tool_fn["parameters"]

    # Ensure exposed schema does NOT mark 'kind' as required, preventing Groq 400 schema error
    assert "kind" in params["properties"]
    assert params["properties"]["kind"].get("default") == "forecast"
    assert "kind" not in params.get("required", [])
    assert set(params.get("required", [])) == {"lat", "lon"}

    # 2. Verify Pydantic defaulting
    req_default = WeatherRequest(lat=48.85, lon=2.35)
    assert req_default.kind == "forecast"
    req_current = WeatherRequest(lat=48.85, lon=2.35, kind="current")
    assert req_current.kind == "current"

    # 3. Test execution through coordinator without providing kind
    mock_weather = AsyncMock()
    prov = Provenance(provider="openweather", capability=Capability.WEATHER, retrieved_at=datetime.now(UTC))
    forecast_ret = WeatherForecast(status="ok", coordinate=Coordinate(lat=48.85, lon=2.35), entries=[], provenance=prov)
    current_ret = CurrentWeather(
        coordinate=Coordinate(lat=48.85, lon=2.35),
        temp_c=20.0,
        condition="Clear",
        provenance=prov,
    )
    mock_weather.get_forecast.return_value = forecast_ret
    mock_weather.get_current.return_value = current_ret

    coordinator = PlanningCoordinator(
        llm=MockLLMClient(),
        flights_adapter=None,
        hotels_adapter=None,
        places_adapter=None,
        routing_adapter=None,
        weather_adapter=mock_weather,
    )

    # Call without 'kind' argument
    call_no_kind = ToolCallRequest(id="w1", name="get_weather", arguments={"lat": 48.85, "lon": 2.35})
    res_str, model, status = await coordinator.execute_tool(call_no_kind, mock_authorizer)
    assert status.status.value == "success"
    assert model == forecast_ret
    mock_weather.get_forecast.assert_awaited_once_with(Coordinate(lat=48.85, lon=2.35), mock_authorizer)

    # Call with kind="current"
    call_current = ToolCallRequest(id="w2", name="get_weather", arguments={"lat": 48.85, "lon": 2.35, "kind": "current"})
    res_str2, model2, status2 = await coordinator.execute_tool(call_current, mock_authorizer)
    assert status2.status.value == "success"
    assert model2 == current_ret
    mock_weather.get_current.assert_awaited_once_with(Coordinate(lat=48.85, lon=2.35), mock_authorizer)


@pytest.mark.asyncio
async def test_places_tracing_and_preservation_and_reuse(mock_authorizer, caplog):
    import logging
    from unittest.mock import AsyncMock
    from app.models.common import Coordinate, Provenance, SearchMeta, SearchResult
    from app.models.geo import Place
    from app.core.errors import ToolCallLimitExceeded
    from datetime import datetime, UTC

    prov = Provenance(provider="geoapify_places", capability=Capability.PLACES, retrieved_at=datetime.now(UTC))
    place1 = Place(place_id="p1", name="Eiffel Tower", coordinate=Coordinate(lat=48.858, lon=2.294), provenance=prov)
    place2 = Place(place_id="p2", name="Louvre Museum", coordinate=Coordinate(lat=48.860, lon=2.337), provenance=prov)
    place3 = Place(place_id="p3", name="Notre Dame", coordinate=Coordinate(lat=48.853, lon=2.349), provenance=prov)

    mock_places_adapter = AsyncMock()
    meta = SearchMeta(provider="geoapify_places", capability=Capability.PLACES, retrieved_at=datetime.now(UTC))
    mock_places_adapter.search_places.side_effect = [
        SearchResult(status="ok", items=[place1, place2], meta=meta),
        SearchResult(status="ok", items=[place3], meta=meta),
        ToolCallLimitExceeded("Limit of 4 places call(s) per planning run reached.", capability=Capability.PLACES),
    ]

    coordinator = PlanningCoordinator(
        llm=MockLLMClient(),
        flights_adapter=None,
        hotels_adapter=None,
        places_adapter=mock_places_adapter,
        routing_adapter=None,
        weather_adapter=None,
    )

    call1 = ToolCallRequest(
        id="p1",
        name="search_places",
        arguments={
            "categories": ["tourism.sights", "heritage"],
            "center": {"lat": 48.85, "lon": 2.35},
            "radius_m": 5000,
        },
    )

    with caplog.at_level(logging.INFO):
        # 1. First invocation: executes adapter and traces sanitized info
        _, res1, status1 = await coordinator.execute_tool(call1, mock_authorizer)
        assert status1.status.value == "success"
        assert len(res1.items) == 2
        assert "Places invocation #1: categories=['tourism.sights', 'heritage']" in caplog.text
        assert "reused=False" in caplog.text

        # 2. Identical invocation: reused from cache without hitting adapter again
        caplog.clear()
        _, res2, status2 = await coordinator.execute_tool(call1, mock_authorizer)
        assert status2.status.value == "success"
        assert len(res2.items) == 2
        assert "Places invocation #2 [REUSED]" in caplog.text
        assert mock_places_adapter.search_places.call_count == 1

        # 3. Different search: succeeds and accumulates
        call3 = ToolCallRequest(
            id="p3",
            name="search_places",
            arguments={
                "categories": ["leisure.park"],
                "center": {"lat": 48.85, "lon": 2.35},
                "radius_m": 5000,
            },
        )
        _, res3, status3 = await coordinator.execute_tool(call3, mock_authorizer)
        assert status3.status.value == "success"
        assert len(res3.items) == 1

        # 4. Limit reached / failure on next call: coordinator preserves previously retrieved places
        call4 = ToolCallRequest(
            id="p4",
            name="search_places",
            arguments={
                "categories": ["entertainment.culture"],
                "center": {"lat": 48.85, "lon": 2.35},
                "radius_m": 5000,
            },
        )
        caplog.clear()
        _, res4, status4 = await coordinator.execute_tool(call4, mock_authorizer)
        # Should preserve existing places instead of returning error
        assert status4.status.value == "success"
        assert len(res4.items) == 3
        assert "preserving 3 previously retrieved places" in caplog.text


@pytest.mark.asyncio
async def test_coordinator_serpapi_maps_authorizer_and_caching_and_budget(settings, caplog):
    import logging
    from app.core.authorization import SearchAuthorizer
    from app.providers.serpapi.maps import SerpApiMapsAdapter
    from tests import fixtures
    from tests.conftest import json_transport

    t = json_transport(fixtures.GOOGLE_MAPS_OK)
    maps_adapter = SerpApiMapsAdapter(settings, transport=t.build())

    authorizer = SearchAuthorizer(run_id="serp_run", limits={Capability.PLACES: 4})

    coordinator = PlanningCoordinator(
        llm=MockLLMClient(),
        flights_adapter=None,
        hotels_adapter=None,
        places_adapter=maps_adapter,
        routing_adapter=None,
        weather_adapter=None,
    )

    call1 = ToolCallRequest(
        id="c1",
        name="search_places",
        arguments={
            "categories": ["tourism.sights"],
            "center": {"lat": 48.8566, "lon": 2.3522},
            "radius_m": 10000,
        },
    )

    with caplog.at_level(logging.INFO):
        # 1. First execution: authorizer authorizes Capability.PLACES, maps adapter runs
        _, res1, status1 = await coordinator.execute_tool(call1, authorizer)
        assert status1.status.value == "success"
        assert len(res1.items) == 2
        assert res1.items[0].provenance.provider == "serpapi_google_maps"
        assert authorizer.usage()[Capability.PLACES.value] == 1
        assert "Places invocation #1" in caplog.text
        assert "reused=False" in caplog.text

        # 2. Identical search: served from coordinator cache, no additional authorizer usage
        caplog.clear()
        _, res2, status2 = await coordinator.execute_tool(call1, authorizer)
        assert status2.status.value == "success"
        assert len(res2.items) == 2
        assert authorizer.usage()[Capability.PLACES.value] == 1  # Not incremented
        assert "Places invocation #2 [REUSED]" in caplog.text

        # 3. Simulate calls 3 and 4 with different centers to advance call count
        for i in range(3, 5):
            call_diff = ToolCallRequest(
                id=f"c{i}",
                name="search_places",
                arguments={
                    "categories": ["tourism.sights"],
                    "center": {"lat": 48.8566 + (i * 0.01), "lon": 2.3522},
                    "radius_m": 10000,
                },
            )
            await coordinator.execute_tool(call_diff, authorizer)

        # 4. Call 5: budget exhausted (call_num > 4), reuses previously retrieved places without error
        caplog.clear()
        call5 = ToolCallRequest(
            id="c5",
            name="search_places",
            arguments={
                "categories": ["leisure.park"],
                "center": {"lat": 48.90, "lon": 2.40},
                "radius_m": 5000,
            },
        )
        _, res5, status5 = await coordinator.execute_tool(call5, authorizer)
        assert status5.status.value == "success"
        assert len(res5.items) == 2  # returns previously retrieved places
        assert res5.meta.provider == "serpapi_google_maps"
        assert "BUDGET EXHAUSTED - REUSED" in caplog.text

