"""Places, geocoding and routing models (Geoapify)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.common import Coordinate, Provenance

_CATEGORY = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")


class GeocodeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=1, ge=1, le=5)


class GeocodeResult(BaseModel):
    formatted: str | None = None
    coordinate: Coordinate
    country: str | None = None
    city: str | None = None
    result_type: str | None = None
    confidence: float | None = None
    provenance: Provenance


class PlacesSearchRequest(BaseModel):
    categories: list[str] = Field(min_length=1, max_length=10)
    center: Coordinate
    radius_m: int = Field(default=10_000, ge=100, le=50_000)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("center", mode="before")
    @classmethod
    def _coerce_center(cls, v: Any) -> Any:
        if isinstance(v, Coordinate):
            return v
        if isinstance(v, dict):
            lat = v.get("lat") if "lat" in v else v.get("latitude")
            lon = v.get("lon") if "lon" in v else v.get("longitude")
            if lat is not None and lon is not None:
                try:
                    return {"lat": float(lat), "lon": float(lon)}
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"coordinates must be numbers, got lat={lat!r}, lon={lon!r}") from exc
            raise ValueError(
                f"'center' object must contain numeric 'lat' and 'lon' coordinates, got keys: {list(v.keys())}"
            )
        if isinstance(v, str):
            if "," in v:
                parts = [p.strip() for p in v.split(",", 1)]
                try:
                    return {"lat": float(parts[0]), "lon": float(parts[1])}
                except ValueError:
                    pass
            raise ValueError(
                f"'center' must be an object with numeric 'lat' and 'lon' fields (e.g. {{'lat': 35.6762, 'lon': 139.6503}}). "
                f"Received string {v!r}. Destination coordinates from context should be used as the center object."
            )
        return v

    @field_validator("categories")
    @classmethod
    def _valid_categories(cls, v: list[str]) -> list[str]:
        for c in v:
            if not _CATEGORY.match(c):
                raise ValueError(f"invalid Geoapify category: {c!r}")
        return v


class Place(BaseModel):
    place_id: str | None = None
    name: str | None = None
    categories: list[str] = Field(default_factory=list)
    address: str | None = None
    city: str | None = None
    coordinate: Coordinate
    distance_from_center_m: float | None = None
    opening_hours: str | None = Field(
        default=None, description="Raw OSM opening_hours string exactly as returned; None if absent."
    )
    website: str | None = None
    phone: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    description: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    provenance: Provenance


ROUTING_MODES = {
    "drive", "light_truck", "medium_truck", "truck", "heavy_truck", "truck_dangerous_goods",
    "long_truck", "bus", "scooter", "motorcycle", "bicycle", "mountain_bike", "road_bike",
    "walk", "hike", "transit", "approximated_transit",
}


class RouteRequest(BaseModel):
    waypoints: list[Coordinate] = Field(min_length=2, max_length=10)
    mode: str = "drive"
    include_geometry: bool = True

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in ROUTING_MODES:
            raise ValueError(f"unsupported routing mode {v!r}")
        return v


class RouteLeg(BaseModel):
    distance_m: float | None = None
    duration_s: float | None = None


class Route(BaseModel):
    mode: str | None = None
    distance_m: float | None = None
    duration_s: float | None = None
    legs: list[RouteLeg] = Field(default_factory=list)
    geometry: list[list[list[float]]] = Field(
        default_factory=list, description="MultiLineString coordinates as [lon, lat] pairs."
    )
    waypoints: list[Coordinate] = Field(default_factory=list)
    provenance: Provenance
