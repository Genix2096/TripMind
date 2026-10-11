"""Geoapify Places API v2 and Geocoding adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.core.errors import ProviderResponseError
from app.models.common import (
    Capability,
    Coordinate,
    Provenance,
    SearchMeta,
    SearchResult,
)
from app.models.geo import GeocodeRequest, GeocodeResult, Place, PlacesSearchRequest
from app.providers.base import BaseAdapter, as_dict, as_float, as_list, as_str, utcnow
from app.providers.geoapify.common import get_geoapify_key

PROVIDER = "geoapify_places"
PLACES_URL = "https://api.geoapify.com/v2/places"
GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"


class GeoapifyPlacesAdapter(BaseAdapter):
    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)

    # ---- Places -----------------------------------------------------------------------
    @staticmethod
    def build_places_params(req: PlacesSearchRequest) -> dict[str, Any]:
        c = req.center
        return {
            "categories": ",".join(req.categories),
            "filter": f"circle:{c.lon},{c.lat},{req.radius_m}",
            "bias": f"proximity:{c.lon},{c.lat}",
            "limit": req.limit,
        }

    async def search_places(
        self, req: PlacesSearchRequest, authorizer: SearchAuthorizer
    ) -> SearchResult[Place]:
        key = get_geoapify_key(self._settings, provider=PROVIDER, capability=Capability.PLACES)
        params = self.build_places_params(req)
        authorizer.authorize(Capability.PLACES, search_fingerprint=fingerprint(PROVIDER, params))
        payload = await self._http.request_json(
            "GET",
            PLACES_URL,
            capability=Capability.PLACES,
            secrets=[key],
            params={**params, "apiKey": key},
        )
        return self.parse_places(payload, params, retrieved_at=utcnow())

    @staticmethod
    def parse_places(
        payload: Any, params: dict[str, Any], *, retrieved_at: datetime
    ) -> SearchResult[Place]:
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ProviderResponseError(
                f"{PROVIDER} returned an unexpected response shape.",
                provider=PROVIDER,
                capability=Capability.PLACES,
            )
        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.PLACES,
            retrieved_at=retrieved_at,
            request_params=params,
            limitations=[
                "Places come from OpenStreetMap-derived data; entrance fees and ratings are not provided.",
                "opening_hours is the raw OSM string and is None when the provider has no hours.",
            ],
        )
        places: list[Place] = []
        skipped = 0
        for feature in payload["features"]:
            place = _parse_place(feature, retrieved_at)
            if place is None:
                skipped += 1
            else:
                places.append(place)
        if skipped:
            meta.warnings.append(f"Skipped {skipped} place(s) without usable coordinates.")
        return SearchResult(status="ok" if places else "empty", items=places, meta=meta)

    # ---- Geocoding --------------------------------------------------------------------
    @staticmethod
    def build_geocode_params(req: GeocodeRequest) -> dict[str, Any]:
        return {"text": req.text, "limit": req.limit, "format": "json"}

    async def geocode(
        self, req: GeocodeRequest, authorizer: SearchAuthorizer
    ) -> SearchResult[GeocodeResult]:
        key = get_geoapify_key(self._settings, provider=PROVIDER, capability=Capability.GEOCODING)
        params = self.build_geocode_params(req)
        authorizer.authorize(Capability.GEOCODING, search_fingerprint=fingerprint(PROVIDER, params))
        payload = await self._http.request_json(
            "GET",
            GEOCODE_URL,
            capability=Capability.GEOCODING,
            secrets=[key],
            params={**params, "apiKey": key},
        )
        return self.parse_geocode(payload, params, retrieved_at=utcnow())

    @staticmethod
    def parse_geocode(
        payload: Any, params: dict[str, Any], *, retrieved_at: datetime
    ) -> SearchResult[GeocodeResult]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ProviderResponseError(
                f"{PROVIDER} returned an unexpected geocoding response shape.",
                provider=PROVIDER,
                capability=Capability.GEOCODING,
            )
        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.GEOCODING,
            retrieved_at=retrieved_at,
            request_params=params,
        )
        results: list[GeocodeResult] = []
        for raw in payload["results"]:
            d = as_dict(raw)
            lat, lon = as_float(d.get("lat")), as_float(d.get("lon"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            results.append(
                GeocodeResult(
                    formatted=as_str(d.get("formatted")),
                    coordinate=Coordinate(lat=lat, lon=lon),
                    country=as_str(d.get("country")),
                    city=as_str(d.get("city")),
                    result_type=as_str(d.get("result_type")),
                    confidence=as_float(as_dict(d.get("rank")).get("confidence")),
                    provenance=Provenance(
                        provider=PROVIDER,
                        capability=Capability.GEOCODING,
                        retrieved_at=retrieved_at,
                        provider_id=as_str(d.get("place_id")),
                        raw=d,
                    ),
                )
            )
        return SearchResult(status="ok" if results else "empty", items=results, meta=meta)


def _parse_place(feature: Any, retrieved_at: datetime) -> Place | None:
    f = as_dict(feature)
    props = as_dict(f.get("properties"))
    lat, lon = as_float(props.get("lat")), as_float(props.get("lon"))
    if lat is None or lon is None:
        coords = as_list(as_dict(f.get("geometry")).get("coordinates"))
        if len(coords) >= 2:
            lon, lat = as_float(coords[0]), as_float(coords[1])
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None

    raw_ds = as_dict(as_dict(props.get("datasource")).get("raw"))
    opening = as_str(props.get("opening_hours")) or as_str(raw_ds.get("opening_hours"))
    website = as_str(props.get("website")) or as_str(raw_ds.get("website"))
    phone = as_str(props.get("phone")) or as_str(raw_ds.get("phone"))
    name = as_str(props.get("name"))
    place_id = as_str(props.get("place_id"))

    missing = [
        label
        for label, value in (("name", name), ("opening_hours", opening), ("website", website))
        if value is None
    ]
    return Place(
        place_id=place_id,
        name=name,
        categories=[c for c in as_list(props.get("categories")) if isinstance(c, str)],
        address=as_str(props.get("formatted")),
        city=as_str(props.get("city")),
        coordinate=Coordinate(lat=lat, lon=lon),
        distance_from_center_m=as_float(props.get("distance")),
        opening_hours=opening,
        website=website,
        phone=phone,
        missing_fields=missing,
        provenance=Provenance(
            provider=PROVIDER,
            capability=Capability.PLACES,
            retrieved_at=retrieved_at,
            provider_id=place_id,
            raw={k: v for k, v in props.items() if k != "datasource"},
        ),
    )
