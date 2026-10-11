from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.coordinator import PlanningCoordinator
from app.agents.flight import FlightResearchAgent
from app.agents.synthesis import ItinerarySynthesisAgent
from app.agents.understanding import TravelRequestUnderstandingAgent
from app.api.deps import get_coordinator
from app.core.authorization import SearchAuthorizer
from app.core.config import Settings
from app.core.errors import (
    LLMOutputError,
    MissingCredentialsError,
    ProviderRequestError,
    ProviderUnavailableError,
)
from app.main import create_app
from app.core.quota import TokenQuotaManager
from app.models.common import Capability
from app.models.itinerary import Activity, DayPlan, LLMSynthesisOutput
from app.models.trip import Budget, TripState
from app.providers.gemini.client import GeminiClient, GeminiUnderstandingClient
from app.providers.groq.client import GroqLLMClient, LLMResponse


class MockGeminiSynthesisClient:
    def __init__(self, expected_output=None, should_raise=None):
        self.expected_output = expected_output
        self.should_raise = should_raise
        self.calls = []

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type, authorizer: SearchAuthorizer, **kwargs
    ) -> Any:
        authorizer.authorize(Capability.UNDERSTANDING, search_fingerprint="mock_fp")
        self.calls.append({"messages": messages, "schema": schema})
        if self.should_raise:
            raise self.should_raise
        return self.expected_output

    async def synthesize(
        self, context: str, authorizer: SearchAuthorizer, **kwargs
    ) -> LLMSynthesisOutput:
        authorizer.authorize(Capability.UNDERSTANDING, search_fingerprint="mock_fp_synth")
        self.calls.append({"context": context})
        if self.should_raise:
            raise self.should_raise
        return self.expected_output


@pytest.fixture
def authorizer():
    return SearchAuthorizer(run_id="test_run", limits={Capability.UNDERSTANDING: 10, Capability.LLM: 10})


@pytest.mark.asyncio
async def test_successful_gemini_itinerary_synthesis(authorizer):
    expected_output = LLMSynthesisOutput(
        trip_summary="A wonderful 3-day trip to Paris.",
        day_wise=[
            DayPlan(
                date=date(2027, 4, 1),
                title="Day 1: Arrival & Louvre",
                activities=[Activity(name="Louvre Museum", description="Art museum tour")],
            ),
            DayPlan(
                date=date(2027, 4, 2),
                title="Day 2: Eiffel Tower",
                activities=[Activity(name="Eiffel Tower", description="Panoramic city views")],
            ),
            DayPlan(
                date=date(2027, 4, 3),
                title="Day 3: Departure",
                activities=[Activity(name="Notre Dame", description="Historical visit")],
            ),
        ],
        validation_warnings=[],
    )
    client = MockGeminiSynthesisClient(expected_output=expected_output)
    agent = ItinerarySynthesisAgent(client)

    result = await agent.synthesize("Flights: CDG, Hotels: Hilton, Places: Eiffel Tower", authorizer)

    assert result == expected_output
    assert result.trip_summary == "A wonderful 3-day trip to Paris."
    assert len(result.day_wise) == 3
    assert authorizer.usage()[Capability.UNDERSTANDING.value] == 1


def test_gemini_schema_normalization_preserves_dayplan_title():
    settings = Settings(_env_file=None)
    client = GeminiUnderstandingClient(settings)

    schema = LLMSynthesisOutput.model_json_schema()
    normalized = client._normalize_schema(schema)

    # Verify that DayPlan.title property is preserved in normalized schema
    day_plan_props = normalized["$defs"]["DayPlan"]["properties"]
    assert "title" in day_plan_props
    assert day_plan_props["title"] == {"type": "string"}

    # Verify schema annotation title and default outside properties are stripped
    assert "title" not in normalized
    assert "default" not in normalized["$defs"]["DayPlan"]["properties"]["weather_summary"]


@pytest.mark.asyncio
async def test_gemini_complete_structured_validation_error(authorizer):
    settings = Settings(_env_file=None, gemini_api_key="mock-key")
    client = GeminiUnderstandingClient(settings)

    # Mock genai client to return invalid json that violates LLMSynthesisOutput schema
    mock_response = MagicMock()
    mock_response.text = '{"invalid_field": "test"}'  # Missing required trip_summary

    mock_aio = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("google.genai.Client") as mock_genai_cls:
        mock_instance = MagicMock()
        mock_instance.aio = mock_aio
        mock_genai_cls.return_value = mock_instance

        with pytest.raises(LLMOutputError) as exc_info:
            await client.synthesize("test context", authorizer)

        assert "did not match the required structure" in str(exc_info.value)
        assert exc_info.value.capability == Capability.UNDERSTANDING


@pytest.mark.asyncio
async def test_gemini_missing_credentials(authorizer):
    settings = Settings(_env_file=None, gemini_api_key=None)
    client = GeminiUnderstandingClient(settings)

    with pytest.raises(MissingCredentialsError) as exc_info:
        await client.synthesize("test context", authorizer)

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert exc_info.value.capability == Capability.UNDERSTANDING


@pytest.mark.asyncio
async def test_gemini_empty_response_handling(authorizer):
    settings = Settings(_env_file=None, gemini_api_key="mock-key")
    client = GeminiUnderstandingClient(settings)

    mock_response = MagicMock()
    mock_response.text = ""  # Empty text

    mock_aio = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("google.genai.Client") as mock_genai_cls:
        mock_instance = MagicMock()
        mock_instance.aio = mock_aio
        mock_genai_cls.return_value = mock_instance

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await client.synthesize("test context", authorizer)

        assert "empty response" in str(exc_info.value)


def test_preservation_of_all_requested_travel_days(settings):
    trip_state = TripState(
        origin="NYC",
        destination="PAR",
        departure_date=date(2027, 5, 10),
        return_date=date(2027, 5, 14),
        budget=Budget(amount=5000, currency="USD", basis="total"),
    )
    # Gemini returns only 2 days, but 5 days were requested
    partial_synthesis = LLMSynthesisOutput(
        trip_summary="A short visit to Paris.",
        day_wise=[
            DayPlan(date=date(2027, 5, 10), title="Arrival", activities=[]),
            DayPlan(date=date(2027, 5, 11), title="Museums", activities=[]),
        ],
        validation_warnings=[],
    )

    from tests.test_workflow import MockAdapter, MockLLMClient, get_events

    mock_groq = MockLLMClient()
    mock_gemini = MockLLMClient()
    mock_gemini.expected_structured = {
        "trip_state": trip_state,
        "synthesis": partial_synthesis,
    }

    coord = PlanningCoordinator(
        llm=mock_groq,
        flights_adapter=MockAdapter(),
        hotels_adapter=MockAdapter(),
        places_adapter=MockAdapter(),
        routing_adapter=MockAdapter(),
        weather_adapter=MockAdapter(),
        understanding_llm=mock_gemini,
        synthesis_llm=mock_gemini,
    )

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: coord

    with TestClient(app) as test_client:
        res = test_client.post("/api/plan", json={"request": "5 days in Paris"})
        assert res.status_code == 200
        events = get_events(test_client, res.json()["session_id"])

    completed_event = next(e for e in events if e["stage"] == "completed")
    day_wise = completed_event["data"]["itinerary"]["day_wise"]

    # All 5 calendar days must be preserved
    assert len(day_wise) == 5
    dates = [d["date"] for d in day_wise]
    assert dates == ["2027-05-10", "2027-05-11", "2027-05-12", "2027-05-13", "2027-05-14"]
    assert "Day 5: Return Journey" in day_wise[4]["title"]


def test_partial_results_when_gemini_synthesis_fails(settings):
    trip_state = TripState(
        origin="NYC",
        destination="PAR",
        departure_date=date(2027, 5, 10),
        return_date=date(2027, 5, 12),
        budget=Budget(amount=3000, currency="USD", basis="total"),
    )

    from tests.test_workflow import MockAdapter, MockLLMClient, get_events

    mock_groq = MockLLMClient()
    mock_gemini = MockLLMClient()
    mock_gemini.expected_structured = {
        "trip_state": trip_state,
        "synthesis": LLMOutputError("Gemini output schema validation failed"),
    }

    coord = PlanningCoordinator(
        llm=mock_groq,
        flights_adapter=MockAdapter(),
        hotels_adapter=MockAdapter(),
        places_adapter=MockAdapter(),
        routing_adapter=MockAdapter(),
        weather_adapter=MockAdapter(),
        understanding_llm=mock_gemini,
        synthesis_llm=mock_gemini,
    )

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: coord

    with TestClient(app) as test_client:
        res = test_client.post("/api/plan", json={"request": "3 days in Paris"})
        assert res.status_code == 200
        events = get_events(test_client, res.json()["session_id"])

    completed_event = next(e for e in events if e["stage"] == "completed")
    itinerary = completed_event["data"]["itinerary"]

    # Must be marked as partial itinerary
    assert "partial itinerary" in itinerary["trip_summary"].lower()
    assert any("Synthesis failed" in w for w in itinerary["validation_warnings"])
    # All 3 travel days must still be preserved
    assert len(itinerary["day_wise"]) == 3
    for dp in itinerary["day_wise"]:
        assert any("synthesis unavailable" in m.lower() for m in dp["missing_information"])


@pytest.mark.asyncio
async def test_no_groq_quota_reservation_for_synthesis(authorizer):
    expected_output = LLMSynthesisOutput(
        trip_summary="Trip to Rome",
        day_wise=[DayPlan(date=date(2027, 7, 1), title="Day 1", activities=[])],
        validation_warnings=[],
    )
    gemini_client = MockGeminiSynthesisClient(expected_output=expected_output)
    agent = ItinerarySynthesisAgent(gemini_client)

    # Track Groq quota acquire calls
    quota_mgr = TokenQuotaManager.get_instance()
    with patch.object(quota_mgr, "acquire", wraps=quota_mgr.acquire) as mock_acquire:
        res = await agent.synthesize("Rome travel context", authorizer)
        assert res == expected_output
        # Groq quota manager must NOT be called for synthesis
        assert mock_acquire.call_count == 0


@pytest.mark.asyncio
async def test_continued_groq_quota_accounting_for_specialist_agents(settings, authorizer):
    from tests import fixtures
    from tests.conftest import json_transport

    t = json_transport(fixtures.GROQ_OK)
    groq_client = GroqLLMClient(settings, transport=t.build())
    quota_mgr = TokenQuotaManager.get_instance()
    quota_mgr.reservations.clear()

    with patch.object(quota_mgr, "acquire", wraps=quota_mgr.acquire) as mock_acquire, \
         patch.object(quota_mgr, "reconcile", wraps=quota_mgr.reconcile) as mock_reconcile:

        resp = await groq_client.chat(
            [{"role": "user", "content": "Search flights"}],
            authorizer,
            max_tokens=200,
        )

        assert resp.content is not None
        # Specialist agent calling Groq must acquire and reconcile quota
        assert mock_acquire.call_count == 1
        assert mock_reconcile.call_count == 1
