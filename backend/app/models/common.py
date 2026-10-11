"""Shared value types: capabilities, money, provenance and search results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field


class Capability(str, Enum):
    """External capabilities. Each one maps to quota-consuming provider calls (LLM included)."""

    FLIGHTS = "flights"
    HOTELS = "hotels"
    PLACES = "places"
    GEOCODING = "geocoding"
    ROUTING = "routing"
    WEATHER = "weather"
    LLM = "llm"
    UNDERSTANDING = "understanding"


class Money(BaseModel):
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)


class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Provenance(BaseModel):
    """Where an external fact came from. Never fabricated: fields are None when unsupplied."""

    provider: str
    capability: Capability
    retrieved_at: datetime
    provider_id: str | None = None
    source_url: str | None = None
    search_id: str | None = None
    raw: dict[str, Any] | None = Field(
        default=None, description="Original provider-returned fields for this entity."
    )


class SearchMeta(BaseModel):
    provider: str
    capability: Capability
    retrieved_at: datetime
    request_params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters sent to the provider (credentials removed)."
    )
    provider_search_id: str | None = None
    provider_search_url: str | None = None
    next_page_token: str | None = None
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider_extras: dict[str, Any] = Field(default_factory=dict)


T = TypeVar("T")


class SearchResult(BaseModel, Generic[T]):
    """A *successful* provider search. status == 'empty' means the search ran and found nothing.

    Failures are never represented here; they raise a ProviderError.
    """

    status: Literal["ok", "empty"]
    items: list[T] = Field(default_factory=list)
    meta: SearchMeta
