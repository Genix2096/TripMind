import json
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.coordinator import PlanningCoordinator
from app.api.deps import get_coordinator
from app.core.authorization import SearchAuthorizer
from app.main import create_app
from app.models.itinerary import DayPlan, LLMSynthesisOutput
from app.models.trip import Budget, TripState
from app.providers.groq.client import LLMResponse


class MockLLMClient:
    def __init__(self, expected_structured=None, expected_chat=None, peer=None):
        self.expected_structured = expected_structured
        self.expected_chat = expected_chat or LLMResponse(content="Mocked text response")
        self.peer = peer
        self.calls = []

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type, authorizer: SearchAuthorizer, **kwargs
    ) -> Any:
        self.calls.append(("structured", messages))
        if callable(self.expected_structured):
            return self.expected_structured(schema)
        # return the configured structured response depending on the schema
        val = None
        if schema == TripState:
            val = (self.expected_structured or {}).get("trip_state") if isinstance(self.expected_structured, dict) else None
            if val is None and self.peer and isinstance(self.peer.expected_structured, dict):
                val = self.peer.expected_structured.get("trip_state")
        elif schema == LLMSynthesisOutput:
            val = (self.expected_structured or {}).get("synthesis") if isinstance(self.expected_structured, dict) else None
            if val is None and self.peer and isinstance(self.peer.expected_structured, dict):
                val = self.peer.expected_structured.get("synthesis")

        if isinstance(val, Exception):
            raise val
        return val

    async def chat(
        self, messages: list[dict[str, Any]], authorizer: SearchAuthorizer, **kwargs
    ) -> LLMResponse:
        self.calls.append(("chat", messages))
        return self.expected_chat


class MockAdapter:
    pass


@pytest.fixture
def mock_coord():
    llm = MockLLMClient()
    gemini = MockLLMClient(peer=llm)
    return PlanningCoordinator(
        llm=llm,
        flights_adapter=MockAdapter(),
        hotels_adapter=MockAdapter(),
        places_adapter=MockAdapter(),
        routing_adapter=MockAdapter(),
        weather_adapter=MockAdapter(),
        understanding_llm=gemini,
        synthesis_llm=gemini,
    )


def get_events(client, session_id):
    stream = client.get(f"/api/plan/{session_id}/stream")
    events = []
    for line in stream.text.strip().split("\n\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_workflow_clarification(settings, mock_coord):
    # Mock understanding to return missing info (empty TripState has missing fields)
    mock_coord.understanding_llm.expected_structured = {
        "trip_state": TripState(clarification_question="Missing info")
    }

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: mock_coord

    with TestClient(app) as client:
        res = client.post("/api/plan", json={"request": "fly to london"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        events = get_events(client, session_id)

    stages = [e["stage"] for e in events]
    assert "clarification_needed" in stages
    assert "completed" not in stages
    assert "error" not in stages


def test_workflow_successful_completion(settings, mock_coord):
    # Provide complete trip state and valid synthesis
    trip_state = TripState(
        origin="NYC", destination="LON", departure_date=date(2027, 1, 1), return_date=date(2027, 1, 7),
        budget=Budget(amount=5000, currency="USD", basis="total")
    )
    synthesis = LLMSynthesisOutput(
        trip_summary="A fun trip to London",
        day_wise=[DayPlan(title="Day 1", activities=[{"name": "Arrive"}])],
        validation_warnings=[],
    )
    mock_coord.understanding_llm.expected_structured = {
        "trip_state": trip_state,
    }
    mock_coord.llm.expected_structured = {
        "synthesis": synthesis,
    }

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: mock_coord

    with TestClient(app) as client:
        res = client.post("/api/plan", json={"request": "fly from NYC to London"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        events = get_events(client, session_id)

    stages = [e["stage"] for e in events]
    print("STAGES:", stages)
    print("EVENTS:", events)
    assert "clarification_needed" not in stages
    assert "completed" in stages

    # Ensure context was passed to agent prompts
    chat_calls = [c[1] for c in mock_coord.llm.calls if c[0] == "chat"]
    prompts_with_context = [
        call for call in chat_calls if any("Context: " in msg.get("content", "") for msg in call)
    ]
    # Flight, Hotel, Places, Routing (Weather is skipped due to horizon) -> 4 calls
    assert len(prompts_with_context) >= 4


def test_workflow_early_termination_on_error(settings, mock_coord):
    # Simulate an exception in the workflow
    mock_coord.understanding_llm.expected_structured = {"trip_state": Exception("Simulated Error")}

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: mock_coord

    with TestClient(app) as client:
        res = client.post("/api/plan", json={"request": "trigger error"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        events = get_events(client, session_id)

    stages = [e["stage"] for e in events]
    assert "error" in stages
    assert "completed" not in stages

def test_synthesis_graceful_failure(settings, mock_coord):
    # synthesis throws an error, but the workflow still completes with a partial itinerary
    trip_state = TripState(
        origin="NYC", destination="LON", departure_date=date(2027, 1, 1), return_date=date(2027, 1, 7),
        budget=Budget(amount=5000, currency="USD", basis="total")
    )
    mock_coord.understanding_llm.expected_structured = {
        "trip_state": trip_state,
    }
    mock_coord.llm.expected_structured = {
        "synthesis": Exception("Synthesis mock failure"),
    }

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: mock_coord

    with TestClient(app) as client:
        res = client.post("/api/plan", json={"request": "fly from NYC to London"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        events = get_events(client, session_id)

    stages = [e["stage"] for e in events]
    assert "completed" in stages
    
    # check the final event
    completed_event = next(e for e in events if e["stage"] == "completed")
    itinerary = completed_event["data"]["itinerary"]
    assert "Synthesis mock failure" in itinerary["trip_summary"]
    assert "Synthesis failed" in itinerary["validation_warnings"][0]


def test_workflow_duration_all_travel_days_included(settings, mock_coord):
    trip_state = TripState(
        origin="NYC",
        destination="LON",
        departure_date=date(2027, 5, 10),
        return_date=date(2027, 5, 14),
        budget=Budget(amount=5000, currency="USD", basis="total"),
    )
    # Synthesis agent returns only 2 days originally
    synthesis = LLMSynthesisOutput(
        trip_summary="Trip to London",
        day_wise=[
            DayPlan(date=date(2027, 5, 10), title="Arrival", activities=[]),
            DayPlan(date=date(2027, 5, 11), title="Museums", activities=[]),
        ],
        validation_warnings=[],
    )
    mock_coord.understanding_llm.expected_structured = {"trip_state": trip_state}
    mock_coord.llm.expected_structured = {"synthesis": synthesis}

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: mock_coord

    with TestClient(app) as client:
        res = client.post("/api/plan", json={"request": "trip to london"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        events = get_events(client, session_id)

    completed_event = next(e for e in events if e["stage"] == "completed")
    itinerary = completed_event["data"]["itinerary"]
    day_wise = itinerary["day_wise"]

    # Must contain all 5 days: May 10, 11, 12, 13, 14 (including return date)
    assert len(day_wise) == 5
    dates = [d["date"] for d in day_wise]
    assert dates == ["2027-05-10", "2027-05-11", "2027-05-12", "2027-05-13", "2027-05-14"]
    # Return date is included as Day 5
    assert "Return Journey" in day_wise[4]["title"] or "Day 5" in day_wise[4]["title"]


def test_workflow_partial_itinerary_when_places_unavailable(settings, mock_coord):
    trip_state = TripState(
        origin="NYC",
        destination="LON",
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 3),
        budget=Budget(amount=3000, currency="USD", basis="total"),
    )
    synthesis = LLMSynthesisOutput(
        trip_summary="A short visit to London.",
        day_wise=[
            DayPlan(date=date(2027, 6, 1), title="Day 1", activities=[]),
            DayPlan(date=date(2027, 6, 2), title="Day 2", activities=[]),
            DayPlan(date=date(2027, 6, 3), title="Day 3", activities=[]),
        ],
        validation_warnings=[],
    )
    mock_coord.understanding_llm.expected_structured = {"trip_state": trip_state}
    mock_coord.llm.expected_structured = {"synthesis": synthesis}

    app = create_app(settings)
    app.dependency_overrides[get_coordinator] = lambda: mock_coord

    with TestClient(app) as client:
        res = client.post("/api/plan", json={"request": "3 days in london"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        events = get_events(client, session_id)

    completed_event = next(e for e in events if e["stage"] == "completed")
    itinerary = completed_event["data"]["itinerary"]

    # Clearly labeled as partial itinerary
    assert "partial itinerary" in itinerary["trip_summary"].lower()
    # Actionable status and warning
    assert itinerary["provider_statuses"]["places"]["status"] == "empty"
    assert any("Attractions data unavailable" in w for w in itinerary["validation_warnings"])
    # Day plans explain missing attraction data
    for dp in itinerary["day_wise"]:
        assert any("unavailable" in m.lower() for m in dp["missing_information"])
from app.core.errors import ProviderRequestError
from app.providers.groq.client import GroqLLMClient


@pytest.mark.asyncio
async def test_oversized_request(settings):
    client = GroqLLMClient(settings)
    authorizer = SearchAuthorizer(limits=settings.call_limits(), run_id="test")
    
    # Large prompt
    messages = [{"role": "user", "content": "A" * 40000}]
    
    with pytest.raises(ProviderRequestError) as exc_info:
        await client.chat(messages, authorizer, max_tokens=2048)
        
    assert "exceeding safe threshold" in str(exc_info.value)
