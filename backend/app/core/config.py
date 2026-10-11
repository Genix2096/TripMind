"""Central settings. Loading settings never contacts any provider."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.common import Capability

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = Field(default="gemini-2.5-pro")
    # Single credential source shared by SerpApi Google Flights, Google Hotels, and Google Maps.
    serpapi_api_key: SecretStr | None = None
    geoapify_api_key: SecretStr | None = None
    openweather_api_key: SecretStr | None = None

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    provider_timeout_seconds: float = 20.0
    llm_timeout_seconds: float = 60.0
    max_request_body_bytes: int = 64_000
    max_user_text_chars: int = 4_000
    log_level: str = "INFO"

    # Hard per-planning-run ceilings on external calls (see app/core/authorization.py).
    limit_flight_searches: int = 2
    limit_hotel_searches: int = 2
    limit_place_searches: int = 4
    limit_geocoding_requests: int = 3
    limit_routing_requests: int = 20
    limit_weather_requests: int = 2
    limit_llm_calls: int = 20
    limit_understanding_calls: int = 10
    limit_tpm: int = 7500

    @field_validator(
        "groq_api_key", "gemini_api_key", "serpapi_api_key", "geoapify_api_key", "openweather_api_key", mode="before"
    )
    @classmethod
    def _blank_secret_is_missing(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    @field_validator("groq_model", "gemini_model", mode="before")
    @classmethod
    def _blank_model_is_missing(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def secret_values(self) -> list[str]:
        values = [
            self.groq_api_key,
            self.gemini_api_key,
            self.serpapi_api_key,
            self.geoapify_api_key,
            self.openweather_api_key,
        ]
        return [v.get_secret_value() for v in values if v is not None]

    def capability_configured(self) -> dict[str, bool]:
        """Presence of credentials only. Never validates them against a provider."""
        return {
            Capability.FLIGHTS.value: self.serpapi_api_key is not None,
            Capability.HOTELS.value: self.serpapi_api_key is not None,
            Capability.PLACES.value: self.serpapi_api_key is not None,
            Capability.GEOCODING.value: self.geoapify_api_key is not None,
            Capability.ROUTING.value: self.geoapify_api_key is not None,
            Capability.WEATHER.value: self.openweather_api_key is not None,
            Capability.LLM.value: self.groq_api_key is not None and self.groq_model is not None,
            Capability.UNDERSTANDING.value: self.gemini_api_key is not None and self.gemini_model is not None,
        }

    def call_limits(self) -> dict[Capability, int]:
        return {
            Capability.FLIGHTS: self.limit_flight_searches,
            Capability.HOTELS: self.limit_hotel_searches,
            Capability.PLACES: self.limit_place_searches,
            Capability.GEOCODING: self.limit_geocoding_requests,
            Capability.ROUTING: self.limit_routing_requests,
            Capability.WEATHER: self.limit_weather_requests,
            Capability.LLM: self.limit_llm_calls,
            Capability.UNDERSTANDING: self.limit_understanding_calls,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
