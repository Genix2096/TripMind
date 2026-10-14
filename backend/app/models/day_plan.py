"""Day-plan models. Kept separate so both itinerary and package models can import them without a cycle."""

from __future__ import annotations

from datetime import date as datetime_date

from pydantic import BaseModel, Field


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
