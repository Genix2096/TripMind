"""Domain models for selectable Travel Packages."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import Money
from app.models.day_plan import DayPlan
from app.models.flights import FlightOption
from app.models.hotels import HotelOption
from app.planning.budget import BudgetReport


class BudgetClassification(str, Enum):
    WITHIN_BUDGET = "within_budget"
    OVER_BUDGET = "over_budget"
    INCOMPLETE = "incomplete"
    NO_BUDGET = "no_budget"


class TravelPackage(BaseModel):
    package_id: str = Field(description="Unique stable ID, e.g. 'package-1'")
    name: str = Field(description="Human-readable package title")
    description: str = Field(description="Short deterministic description of how the package was selected")
    target_tier: str = Field(description="'within_budget', 'over_budget', 'unclassified' or 'incomplete'")
    budget_classification: BudgetClassification = Field(description="Deterministic budget classification")

    # Selected primary options
    selected_outbound_flight: FlightOption | None = None
    selected_return_flight: FlightOption | None = None
    selected_hotel: HotelOption | None = None

    # Available alternatives for this package (selection is validated against these)
    outbound_flight_alternatives: list[FlightOption] = Field(default_factory=list)
    return_flight_alternatives: list[FlightOption] = Field(default_factory=list)
    hotel_alternatives: list[HotelOption] = Field(default_factory=list)

    # Itinerary tailored to this package's selections
    day_wise: list[DayPlan] = Field(default_factory=list)
    trip_summary: str = Field(default="")

    # Independent budget breakdown
    budget_report: BudgetReport
    total_cost: Money | None = Field(
        default=None, description="Only set when every priced component is known (never a partial sum)."
    )
    known_subtotal: Money | None = Field(
        default=None, description="Sum of known component prices; a lower bound when the package is incomplete."
    )
    remaining_budget: Money | None = None
    amount_over_budget: Money | None = None
    currency: str = "USD"

    # Status, warnings and provenance
    is_complete: bool = True
    completeness_status: str = "complete"
    warnings: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    provenance_summary: dict[str, Any] = Field(default_factory=dict)


class PackageRecalculateRequest(BaseModel):
    """Selection by ID only. Prices, trip dates, traveler counts and budget are never read from the client."""

    session_id: str = Field(min_length=1, max_length=64)
    package_id: str = Field(min_length=1, max_length=64)
    outbound_flight_id: str | None = Field(default=None, max_length=64)
    return_flight_id: str | None = Field(default=None, max_length=64)
    hotel_id: str | None = Field(default=None, max_length=64)


class PackageRecalculateResponse(BaseModel):
    package: TravelPackage
