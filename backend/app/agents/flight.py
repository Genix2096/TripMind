from typing import Any

from app.agents.base import Agent
from app.models.flights import FlightSearchRequest


class FlightResearchAgent(Agent):
    """Agent 2: Flight Research Agent"""
    
    @property
    def system_prompt(self) -> str:
        return (
            "You are the Flight Research Agent. Your job is to search for flights using the provided tool, "
            "compare the candidates, evaluate their price, duration, stops, and schedule, and return a structured summary. "
            "Do not invent flights. Use only the results returned by the search tool."
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        # Using model_json_schema, but we must make sure the schema is compatible with Groq's tool expectations
        schema = FlightSearchRequest.model_json_schema()
        # Remove $defs if any to simplify, or keep them if Groq supports them
        # OpenAI supports standard JSON Schema.
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_flights",
                    "description": "Search for flights using Google Flights.",
                    "parameters": schema
                }
            }
        ]
