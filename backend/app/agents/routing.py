from typing import Any

from app.agents.base import Agent
from app.models.geo import RouteRequest


class RoutingAndSchedulingAgent(Agent):
    """Agent 5: Routing and Scheduling Agent"""
    
    @property
    def system_prompt(self) -> str:
        return (
            "You are the Routing and Scheduling Agent. Your job is to estimate travel times between itinerary stops "
            "using the provided routing tool. Organize attractions into a feasible sequence and detect conflicts. "
            "Do not invent travel times or route distances."
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "route",
                    "description": "Estimate journey duration and distance between waypoints using Geoapify.",
                    "parameters": RouteRequest.model_json_schema()
                }
            }
        ]
