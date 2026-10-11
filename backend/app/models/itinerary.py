from __future__ import annotations

from datetime import date as datetime_date
from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import Capability
from app.models.flights import FlightOption
from app.models.hotels import HotelOption


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



class Activity(BaseModel):
    name: str
    location: str | None = None
    description: str | None = None
    time_window: str | None = Field(default=None, description="Only when supported by opening hours or scheduled.")
    estimated_duration: str | None = Field(default=None, description="Only when available or explicitly identified as an estimate.")
    travel_info: str | None = Field(default=None, description="Route distances and travel durations if returned by routing.")
    data_source: str | None = Field(default=None, description="Provenance where appropriate.")

class DayPlan(BaseModel):
    date: datetime_date | None = None
    title: str
    activities: list[Activity] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    weather_summary: str | None = None
    scheduling_conflicts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

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
