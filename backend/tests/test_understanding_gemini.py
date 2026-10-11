import pytest
from datetime import date
from typing import Any

from app.models.trip import TripState
from app.agents.understanding import TravelRequestUnderstandingAgent
from app.core.authorization import SearchAuthorizer
from app.models.common import Capability


class MockGeminiClient:
    def __init__(self, expected_structured=None, should_raise=None):
        self.expected_structured = expected_structured
        self.should_raise = should_raise
        self.calls = []

    async def complete_structured(self, messages: list[dict[str, Any]], schema: type, authorizer: SearchAuthorizer, **kwargs) -> Any:
        self.calls.append({"messages": messages, "schema": schema})
        if self.should_raise:
            raise self.should_raise
        return self.expected_structured


@pytest.fixture
def mock_authorizer():
    return SearchAuthorizer(run_id="test", limits={Capability.UNDERSTANDING: 5})


@pytest.mark.asyncio
async def test_gemini_understanding_complete_request(mock_authorizer):
    trip_state = TripState(
        origin="San Francisco",
        destination="Tokyo",
        departure_date=date(2027, 4, 1),
        return_date=date(2027, 4, 10),
        budget=None,
    )
    client = MockGeminiClient(expected_structured=trip_state)
    agent = TravelRequestUnderstandingAgent(client)
    
    result = await agent.understand("I want to fly from San Francisco to Tokyo from April 1 to 10 next year.", date(2026, 10, 10), mock_authorizer)
    
    assert result.origin == "San Francisco"
    assert result.destination == "Tokyo"
    assert result.departure_date == date(2027, 4, 1)
    assert result.return_date == date(2027, 4, 10)
    assert len(client.calls) == 1
    
    sys_msg = next((m["content"] for m in client.calls[0]["messages"] if m["role"] == "system"), "")
    assert "Today's date is 2026-10-10" in sys_msg


@pytest.mark.asyncio
async def test_gemini_understanding_ambiguous_request(mock_authorizer):
    trip_state = TripState(
        origin="London",
        clarification_question="Where would you like to travel to from London?",
    )
    client = MockGeminiClient(expected_structured=trip_state)
    agent = TravelRequestUnderstandingAgent(client)
    
    result = await agent.understand("I want to travel from London.", date(2026, 10, 10), mock_authorizer)
    
    assert result.origin == "London"
    assert result.destination is None
    assert result.clarification_question == "Where would you like to travel to from London?"


@pytest.mark.asyncio
async def test_gemini_understanding_with_existing_state(mock_authorizer):
    existing_state_json = '{"origin": "London", "destination": "Paris"}'
    
    trip_state = TripState(
        origin="London",
        destination="Paris",
        departure_date=date(2026, 12, 1),
        calendar_days=5
    )
    client = MockGeminiClient(expected_structured=trip_state)
    agent = TravelRequestUnderstandingAgent(client)
    
    result = await agent.understand("Actually, I want to go in December for 5 days.", date(2026, 10, 10), mock_authorizer, existing_state=existing_state_json)
    
    sys_msg = next((m["content"] for m in client.calls[0]["messages"] if m["role"] == "system"), "")
    assert existing_state_json in sys_msg
    assert result.departure_date == date(2026, 12, 1)
    assert result.calendar_days == 5


def test_gemini_schema_normalization():
    from app.providers.gemini.client import GeminiUnderstandingClient
    from app.core.config import Settings
    
    client = GeminiUnderstandingClient(Settings(_env_file=None))
    
    original_schema = TripState.model_json_schema()
    
    # Verify original schema contains exclusiveMinimum
    assert "exclusiveMinimum" in str(original_schema)
    
    # Normalize schema
    normalized = client._normalize_schema(original_schema)
    normalized_str = str(normalized)
    
    # Verify exclusiveMinimum is gone, replaced by minimum
    assert "exclusiveMinimum" not in normalized_str
    assert "exclusiveMaximum" not in normalized_str
    assert "title" not in normalized_str
    assert "default" not in normalized_str
    
    # Validate that Pydantic still enforces budget amount > 0
    from app.models.trip import Budget
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError) as exc:
        Budget(amount=0, currency="USD")
    assert "greater than 0" in str(exc.value)

    budget = Budget(amount=100, currency="USD")
    assert budget.amount == 100


@pytest.mark.asyncio
async def test_gemini_understanding_validation_error(mock_authorizer):
    from app.core.errors import LLMOutputError
    
    # Mock complete_structured to raise an LLMOutputError representing a validation failure
    class ErrorClient:
        async def complete_structured(self, messages, schema, authorizer, **kwargs):
            raise LLMOutputError(
                "The language model returned output that did not match the required structure.",
                details={"error": "1 validation error for TripState\nbudget.amount\n  Input should be greater than 0"}
            )
            
    agent = TravelRequestUnderstandingAgent(ErrorClient())
    result = await agent.understand("I have 0 budget", date(2026, 10, 10), mock_authorizer)
    
    # The agent should catch the error and convert it to a clarification question
    assert result.clarification_question is not None
    assert "Input should be greater than 0" in result.clarification_question
