"""TripState: the validated, typed description of what the user wants.

Nothing here is invented: unknown values stay None and are reported by ``missing_mandatory``.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.flights import TravelClass


class BudgetBasis(str, Enum):
    TOTAL = "total"
    PER_PERSON = "per_person"


class Budget(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    basis: BudgetBasis = BudgetBasis.TOTAL

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    def total_limit(self, travelers: int) -> Decimal:
        return self.amount * travelers if self.basis == BudgetBasis.PER_PERSON else self.amount


class Travelers(BaseModel):
    adults: int = Field(default=1, ge=1, le=20)
    children_ages: list[int] = Field(default_factory=list, max_length=10)

    @field_validator("children_ages")
    @classmethod
    def _ages(cls, v: list[int]) -> list[int]:
        if any(a < 0 or a > 17 for a in v):
            raise ValueError("children ages must be between 0 and 17")
        return v

    @property
    def children(self) -> int:
        return len(self.children_ages)

    @property
    def total(self) -> int:
        return self.adults + self.children


class TravelPace(str, Enum):
    RELAXED = "relaxed"
    MODERATE = "moderate"
    PACKED = "packed"


class TripPreferences(BaseModel):
    interests: list[str] = Field(default_factory=list, max_length=20)
    hotel_category: str | None = Field(default=None, max_length=100)
    accommodation_notes: str | None = Field(default=None, max_length=500)
    food_preferences: list[str] = Field(default_factory=list, max_length=20)
    mobility_requirements: str | None = Field(default=None, max_length=500)
    pace: TravelPace | None = None
    cabin_class: TravelClass | None = None
    preferred_airlines: list[str] = Field(default_factory=list, max_length=10)
    required_activities: list[str] = Field(default_factory=list, max_length=20)
    excluded_activities: list[str] = Field(default_factory=list, max_length=20)
    max_travel_time_minutes: int | None = Field(default=None, ge=10)
    other_constraints: str | None = Field(default=None, max_length=1000)


class HardConstraints(BaseModel):
    """Mandatory limits the deterministic validator enforces. Only set when the user said so."""

    max_flight_stops: int | None = Field(default=None, ge=0, le=2)
    max_flight_duration_minutes: int | None = Field(default=None, ge=30)
    max_flight_total: Decimal | None = Field(default=None, gt=0)
    min_hotel_rating: float | None = Field(default=None, ge=0, le=5)
    min_hotel_class: int | None = Field(default=None, ge=1, le=5)
    max_hotel_total: Decimal | None = Field(default=None, gt=0)
    required_hotel_amenities: list[str] = Field(default_factory=list, max_length=20)


class MissingField(BaseModel):
    field: str
    question: str


class TripState(BaseModel):
    raw_request: str | None = Field(default=None, max_length=4000)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    departure_date: date | None = None
    return_date: date | None = None
    calendar_days: int | None = Field(default=None, ge=1, le=60)
    nights: int | None = Field(default=None, ge=0, le=60)
    travelers: Travelers = Field(default_factory=Travelers)
    rooms: int | None = Field(default=None, ge=1, le=10)
    budget: Budget | None = None
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    
    assumptions: list[str] = Field(default_factory=list, description="Assumptions made by the LLM during interpretation.")
    missing_information: list[str] = Field(default_factory=list, description="Missing essential fields.")
    clarification_question: str | None = Field(default=None, description="A single specific question to ask the user if the request is ambiguous or missing essential info.")

    @model_validator(mode="after")
    def _validate_dates(self) -> TripState:
        # Date order validation
        if self.departure_date and self.return_date and self.return_date < self.departure_date:
            raise ValueError("return_date must not be before departure_date")
            
        # Nights and calendar days calculation
        if self.departure_date and self.return_date:
            calculated_nights = (self.return_date - self.departure_date).days
            calculated_days = calculated_nights + 1
            
            # If the user provided nights or days, validate them against the dates.
            # However, if they conflict, we should ideally ask a clarification question, but the application logic just normalizes them.
            if self.nights is None:
                self.nights = calculated_nights
            if self.calendar_days is None:
                self.calendar_days = calculated_days
        elif self.departure_date and self.nights is not None:
            self.return_date = self.departure_date + timedelta(days=self.nights)
            if self.calendar_days is None:
                self.calendar_days = self.nights + 1
        elif self.departure_date and self.calendar_days is not None:
            self.return_date = self.departure_date + timedelta(days=self.calendar_days - 1)
            if self.nights is None:
                self.nights = self.calendar_days - 1

        return self

    @property
    def resolved_return_date(self) -> date | None:
        return self.return_date

    def missing_mandatory(self) -> list[MissingField]:
        missing = []
        if not self.origin:
            missing.append(MissingField(field="origin", question="Where are you traveling from?"))
        if not self.destination:
            missing.append(MissingField(field="destination", question="Where are you traveling to?"))
        if not self.departure_date:
            missing.append(MissingField(field="departure_date", question="When do you want to depart?"))
        if not self.return_date and not self.calendar_days and not self.nights:
            missing.append(MissingField(field="return_date", question="When will you return or how long is the trip?"))
        if not self.budget:
            missing.append(MissingField(field="budget", question="What is your budget?"))
        if self.clarification_question:
            missing.append(MissingField(field="general", question=self.clarification_question))
        return missing

    def contradictions(self, today: date) -> list[str]:
        """Contradictory or impossible inputs that require a clarification question."""
        problems: list[str] = []
        if self.departure_date and self.departure_date < today:
            problems.append(f"The departure date {self.departure_date} is in the past.")
        if self.origin and self.destination and self.origin.strip().lower() == self.destination.strip().lower():
            problems.append("Origin and destination are the same.")
        return problems
