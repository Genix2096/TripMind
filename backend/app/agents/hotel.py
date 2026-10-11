from typing import Any

from app.agents.base import Agent
from app.models.hotels import HotelSearchRequest


class HotelResearchAgent(Agent):
    """Agent 3: Hotel Research Agent"""
    
    @property
    def system_prompt(self) -> str:
        return (
            "You are the Hotel Research Agent. Your job is to search for hotels using the provided tool, "
            "respect the requested destination, dates, occupancy, budget, and preferences. "
            "Compare the returned candidates, evaluate prices carefully, and return a summary. "
            "Do not invent hotels or prices."
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_hotels",
                    "description": "Search for hotels using Google Hotels.",
                    "parameters": HotelSearchRequest.model_json_schema()
                }
            }
        ]
