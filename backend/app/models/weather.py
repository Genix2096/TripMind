"""Weather models. Current conditions and forecasts are separate types on purpose."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import Coordinate, Provenance


class CurrentWeather(BaseModel):
    observed_at: datetime | None = Field(default=None, description="Provider observation time (UTC).")
    location_name: str | None = None
    coordinate: Coordinate
    temp_c: float | None = None
    feels_like_c: float | None = None
    humidity_pct: int | None = None
    condition: str | None = None
    description: str | None = None
    wind_speed_ms: float | None = None
    clouds_pct: int | None = None
    rain_1h_mm: float | None = None
    provenance: Provenance


class ForecastEntry(BaseModel):
    forecast_time: datetime = Field(description="Start of the 3-hour block (UTC).")
    temp_c: float | None = None
    feels_like_c: float | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_pct: int | None = None
    condition: str | None = None
    description: str | None = None
    precipitation_probability: float | None = Field(default=None, ge=0, le=1)
    wind_speed_ms: float | None = None
    clouds_pct: int | None = None
    rain_3h_mm: float | None = None
    snow_3h_mm: float | None = None


class WeatherForecast(BaseModel):
    status: str  # "ok" | "empty"
    coordinate: Coordinate
    location_name: str | None = None
    timezone_offset_seconds: int | None = None
    entries: list[ForecastEntry] = Field(default_factory=list)
    covers_from: datetime | None = None
    covers_to: datetime | None = None
    provenance: Provenance
