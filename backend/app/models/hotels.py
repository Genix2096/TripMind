"""Hotel request/response models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.common import Coordinate, Money, Provenance


class HotelSort(str, Enum):
    LOWEST_PRICE = "lowest_price"
    HIGHEST_RATING = "highest_rating"
    MOST_REVIEWED = "most_reviewed"


class HotelSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="e.g. 'hotels in Goa, India'")
    check_in: date
    check_out: date
    adults: int = Field(default=2, ge=1, le=20)
    children_ages: list[int] = Field(default_factory=list, max_length=10)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    gl: str | None = Field(default="in", min_length=2, max_length=2)
    hl: str | None = Field(default="en", min_length=2, max_length=5)
    sort_by: Literal["lowest_price", "highest_rating", "most_reviewed"] | None = Field(
        default=None, 
        description="Allowed values: 'lowest_price', 'highest_rating', 'most_reviewed'. Leave null for default sorting."
    )
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    min_rating: float | None = Field(default=None, description="One of 3.5, 4.0, 4.5")
    hotel_classes: list[int] = Field(default_factory=list)
    property_types: list[int] = Field(default_factory=list)
    amenities: list[int] = Field(default_factory=list)
    free_cancellation: bool = False
    next_page_token: str | None = Field(default=None, max_length=2048)

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("children_ages")
    @classmethod
    def _ages(cls, v: list[int]) -> list[int]:
        if any(a < 1 or a > 17 for a in v):
            raise ValueError("children ages must be between 1 and 17 (under-1s are entered as 1)")
        return v

    @field_validator("min_rating")
    @classmethod
    def _rating(cls, v: float | None) -> float | None:
        if v is not None and v not in (3.5, 4.0, 4.5):
            raise ValueError("min_rating must be 3.5, 4.0 or 4.5 (the values Google Hotels supports)")
        return v

    @field_validator("hotel_classes")
    @classmethod
    def _classes(cls, v: list[int]) -> list[int]:
        if any(c not in (2, 3, 4, 5) for c in v):
            raise ValueError("hotel_classes values must be in 2..5")
        return v

    @model_validator(mode="after")
    def _dates(self) -> HotelSearchRequest:
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if (self.check_out - self.check_in).days > 60:
            raise ValueError("stay length above 60 nights is not supported")
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must not exceed max_price")
        return self

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def children(self) -> int:
        return len(self.children_ages)


class HotelPrice(BaseModel):
    """A provider price field. `amount` is None when only display text was returned."""

    amount: Money | None = None
    display_text: str | None = None
    before_taxes_fees: Money | None = None


class HotelPriceSource(BaseModel):
    source: str | None = None
    nightly: Money | None = None
    num_guests: int | None = None


class HotelOption(BaseModel):
    hotel_id: str = Field(description="Local identifier within one search; not a provider fact.")
    name: str | None = None
    property_type: str | None = None
    description: str | None = None
    address: str | None = Field(
        default=None, description="Not supplied by Google Hotels list results; None unless returned."
    )
    coordinates: Coordinate | None = None
    hotel_class: int | None = None
    rating: float | None = None
    review_count: int | None = None
    location_rating: float | None = None
    amenities: list[str] = Field(default_factory=list)
    excluded_amenities: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    check_in_time: str | None = None
    check_out_time: str | None = None
    nightly_rate: HotelPrice | None = Field(
        default=None, description="Provider 'rate_per_night' exactly as returned."
    )
    total_rate: HotelPrice | None = Field(
        default=None, description="Provider 'total_rate' for the whole stay exactly as returned."
    )
    price_sources: list[HotelPriceSource] = Field(default_factory=list)
    link: str | None = None
    property_token: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    provenance: Provenance

    @property
    def total_amount(self) -> Decimal | None:
        return self.total_rate.amount.amount if self.total_rate and self.total_rate.amount else None
