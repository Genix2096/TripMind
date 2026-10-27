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
            "3. The 'center' parameter MUST be a coordinate object with numeric 'lat' and 'lon' fields (e.g. {'lat': 35.6762, 'lon': 139.6503}) using the destination_coordinates provided in the context. Never pass a destination name or string as 'center'.\n"
            "4. Do not invent attractions, opening hours, or ratings."
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_places",
                    "description": "Search for attractions and points of interest around a geographic center coordinate.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of attraction category strings (e.g. ['tourism.sights', 'tourism.attraction', 'heritage', 'leisure.park', 'entertainment.culture']).",
                            },
                            "center": {
                                "type": "object",
                                "description": "Geographic center coordinate object with numeric 'lat' and 'lon' properties from destination_coordinates.",
                                "properties": {
                                    "lat": {
                                        "type": "number",
                                        "minimum": -90.0,
                                        "maximum": 90.0,
                                        "description": "Latitude of the center point.",
                                    },
                                    "lon": {
                                        "type": "number",
                                        "minimum": -180.0,
                                        "maximum": 180.0,
                                        "description": "Longitude of the center point.",
                                    },
                                },
                                "required": ["lat", "lon"],
                            },
                            "radius_m": {
                                "type": "integer",
                                "default": 10000,
                                "minimum": 100,
                                "maximum": 50000,
                                "description": "Search radius in meters (default 10000).",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Maximum number of places to return (default 20).",
                            },
                        },
                        "required": ["categories", "center"],
                    },
                },
            }
        ]
