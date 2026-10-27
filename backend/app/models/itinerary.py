from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import Capability
from app.models.day_plan import Activity, DayPlan  # noqa: F401  (re-exported for existing imports)
from app.models.flights import FlightOption
from app.models.hotels import HotelOption
from app.models.packages import TravelPackage
from app.models.weather import SeasonalWeatherEstimate


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NOT_REQUESTED = "not_requested"

class ProviderResultStatus(BaseModel):
    capability: Capability
    status: ProviderStatus
    error_detail: str | None = None



class LLMSynthesisOutput(BaseModel):
    trip_summary: str = Field(description="A high-level summary of the trip.")
    day_wise: list[DayPlan] = Field(default_factory=list, description="Day-by-day breakdown.")
    validation_warnings: list[str] = Field(default_factory=list, description="Warnings about feasibility.")

class StructuredItinerary(BaseModel):
    trip_summary: str
    flights: list[FlightOption] = Field(default_factory=list)
    hotels: list[HotelOption] = Field(default_factory=list)
    day_wise: list[DayPlan] = Field(default_factory=list)
    budget_report: dict | None = None  # Using dict to avoid serialization issues for now, or use BudgetReport
    provider_statuses: dict[str, ProviderResultStatus] = Field(default_factory=dict)
    validation_warnings: list[str] = Field(default_factory=list)
    packages: list[TravelPackage] = Field(default_factory=list)
    package_notes: list[str] = Field(default_factory=list)
    seasonal_weather: SeasonalWeatherEstimate | None = None
