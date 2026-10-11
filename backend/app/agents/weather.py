from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.base import Agent


class WeatherRequest(BaseModel):
    lat: float
    lon: float
    kind: Literal["current", "forecast"] = Field(
        default="forecast",
        description="Must be exactly 'current' or 'forecast'. Use 'forecast' for trip planning dates, or 'current' for today's weather."
    )


class WeatherAgent(Agent):
    """Agent 6: Weather Agent"""

    @property
    def system_prompt(self) -> str:
        return (
            "You are the Weather Agent. Your job is to retrieve relevant current weather or forecast data "
            "for the requested locations using the get_weather tool, identify risks, and suggest adjustments. "
            "You MUST specify the 'kind' argument: use 'current' if checking today's weather, or 'forecast' for upcoming trip dates. "
            "Do not invent weather conditions. If forecast data is unavailable for future dates, state that clearly."
        )

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather or a 5-day forecast for coordinates using OpenWeather.",
                    "parameters": WeatherRequest.model_json_schema()
                }
            }
        ]
