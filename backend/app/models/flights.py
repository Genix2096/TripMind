"""Flight request/response models. Every optional field stays None when the provider omits it."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.common import Money, Provenance


class PriceScope(str, Enum):
    TOTAL_ALL_TRAVELERS = "total_all_travelers"
    PER_TRAVELER = "per_traveler"
    UNSPECIFIED = "unspecified_by_provider"


class TravelClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class FlightSearchRequest(BaseModel):
    origin: str = Field(description="IATA airport/city code (e.g. MAA) or kgmid (/m/...)")
    destination: str = Field(description="IATA airport/city code (e.g. BKK, LHR) or kgmid (/m/...)")
    outbound_date: date
    return_date: date | None = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    infants_in_seat: int = Field(default=0, ge=0, le=8)
    infants_on_lap: int = Field(default=0, ge=0, le=8)
    travel_class: TravelClass = TravelClass.ECONOMY
    currency: str = Field(default="INR", min_length=3, max_length=3)
    max_stops: int | None = Field(default=None, ge=0, le=2)
    max_duration_minutes: int | None = Field(default=None, ge=30, le=7 * 24 * 60)
    include_airlines: list[str] = Field(default_factory=list)
    exclude_airlines: list[str] = Field(default_factory=list)
    gl: str | None = Field(default="in", min_length=2, max_length=2)
    hl: str | None = Field(default="en", min_length=2, max_length=5)
    departure_token: str | None = Field(
        default=None,
        max_length=4096,
        description="Fetch return-leg options for a chosen outbound flight (a separate paid search).",
    )

    @field_validator("origin", "destination")
    @classmethod
    def _place_code(cls, v: str) -> str:
        v = v.strip()
        if v.startswith(("/m/", "/g/")):
            return v
        v_upper = v.upper()
        # Normalization map for common city names to prevent tool validation errors
        CITY_MAP = {
            "MUMBAI": "BOM", "BOMBAY": "BOM",
            "BANGKOK": "BKK",
            "NEW YORK": "JFK", "NYC": "JFK", "NEW YORK CITY": "JFK",
            "DELHI": "DEL", "NEW DELHI": "DEL",
            "LONDON": "LHR",
            "PARIS": "CDG",
            "TOKYO": "HND",
            "DUBAI": "DXB",
            "SINGAPORE": "SIN",
            "BENGALURU": "BLR", "BANGALORE": "BLR",
            "CHENNAI": "MAA", "MADRAS": "MAA",
            "KOLKATA": "CCU", "CALCUTTA": "CCU",
            "HYDERABAD": "HYD",
            "GOA": "GOI",
            "SAN FRANCISCO": "SFO",
            "LOS ANGELES": "LAX",
            "CHICAGO": "ORD",
            "MIAMI": "MIA",
            "AMSTERDAM": "AMS",
            "FRANKFURT": "FRA",
            "SYDNEY": "SYD",
            "MELBOURNE": "MEL",
            "ROME": "FCO",
            "BARCELONA": "BCN",
        }
        if v_upper in CITY_MAP:
            return CITY_MAP[v_upper]
        if not (len(v_upper) == 3 and v_upper.isalpha()):
            raise ValueError(f"'{v}' must be a 3-letter IATA code or a kgmid such as /m/0f2v0")
        return v_upper

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _consistency(self) -> FlightSearchRequest:
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        if self.return_date and self.return_date < self.outbound_date:
            raise ValueError("return_date must not be before outbound_date")
        if self.include_airlines and self.exclude_airlines:
            raise ValueError("include_airlines and exclude_airlines cannot be combined")
        if self.adults + self.children + self.infants_in_seat > 9:
            raise ValueError("at most 9 seated passengers per search")
        if self.infants_on_lap > self.adults:
            raise ValueError("each lap infant needs an adult")
        return self

    @property
    def travelers(self) -> int:
        return self.adults + self.children + self.infants_in_seat + self.infants_on_lap


class Airport(BaseModel):
    name: str | None = None
    code: str | None = None
    # Provider gives local wall-clock time without a timezone, so this is intentionally naive.
    local_time: datetime | None = None


class FlightSegment(BaseModel):
    airline: str | None = None
    flight_number: str | None = None
    aircraft: str | None = None
    travel_class: str | None = None
    departure: Airport
    arrival: Airport
    duration_minutes: int | None = None
    overnight: bool | None = None
    legroom: str | None = None
    extensions: list[str] = Field(default_factory=list)


class Layover(BaseModel):
    airport_name: str | None = None
    airport_code: str | None = None
    duration_minutes: int | None = None
    overnight: bool | None = None


class FlightOption(BaseModel):
    option_id: str = Field(description="Local identifier within one search; not a provider fact.")
    direction: Literal["outbound", "return"] | None = Field(
        default=None,
        description="Which searched leg produced this option. Set by the search orchestration, not by the provider.",
    )
    segments: list[FlightSegment] = Field(default_factory=list)
    layovers: list[Layover] = Field(default_factory=list)
    total_duration_minutes: int | None = None
    stops: int | None = Field(
        default=None, description="Calculated as len(segments)-1 from returned segments."
    )
    price: Money | None = None
    price_scope: PriceScope = PriceScope.UNSPECIFIED
    trip_type: str | None = None
    provider_ranked_best: bool = Field(
        default=False, description="True when listed in the provider's 'best_flights' group."
    )
    return_leg_details_pending: bool = Field(
        default=False,
        description="Round trip: segments describe the outbound leg only; the return leg needs "
        "another explicit search using departure_token.",
    )
    departure_token: str | None = None
    booking_token: str | None = None
    airline_logo: str | None = None
    carbon_emissions_grams: int | None = None
    missing_fields: list[str] = Field(default_factory=list)
    provenance: Provenance

    @property
    def price_amount(self) -> Decimal | None:
        return self.price.amount if self.price else None
