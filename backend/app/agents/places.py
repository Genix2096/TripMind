from typing import Any

from app.agents.base import Agent
from app.models.geo import PlacesSearchRequest


class PlacesAndActivitiesAgent(Agent):
    """Agent 4: Places and Activities Agent"""
    
    @property
    def system_prompt(self) -> str:
        return (
            "You are the Places and Activities Agent. Your job is to discover real-world attractions and points of interest "
            "using the provided search_places tool. Match them to user interests, evaluate proximity, and return source-backed candidates.\n"
            "IMPORTANT CONSTRAINTS:\n"
            "1. You have a strict limit of at most 4 places calls per planning run.\n"
            "2. In your very first search, you MUST batch the most useful attraction categories for the destination together "
            "in the 'categories' list of a single search_places call (e.g. ['tourism.sights', 'tourism.attraction', 'heritage', 'leisure.park', 'entertainment.culture']). "
            "Do NOT make separate single-category calls.\n"
            "3. Do not invent attractions, opening hours, or ratings."
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_places",
                    "description": "Search for attractions and points of interest using Geoapify.",
                    "parameters": PlacesSearchRequest.model_json_schema()
                }
            }
        ]
