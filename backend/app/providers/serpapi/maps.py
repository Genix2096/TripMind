"""SerpApi Google Maps adapter (engine=google_maps).

Queries the SerpApi Google Maps search engine to discover attractions, sights,
and points of interest, returning normalized Place domain models.
"""

from __future__ import annotations

import math
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
from app.providers.base import (
    BaseAdapter,
    as_dict,
    as_float,
    as_int,
    as_list,
    as_str,
    utcnow,
)
from app.providers.serpapi.common import check_serpapi_payload, get_serpapi_key

PROVIDER = "serpapi_google_maps"
BASE_URL = "https://serpapi.com/search.json"

_RAW_DROP = {"photos_link", "reviews_link", "place_id_search", "thumbnail"}


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates on Earth."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)


class SerpApiMapsAdapter(BaseAdapter):
    """Adapter for SerpApi Google Maps Places discovery."""

    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)

    @staticmethod
    def build_params(req: PlacesSearchRequest, query_text: str | None = None) -> dict[str, Any]:
        """Build search parameters for SerpApi Google Maps engine."""
        if query_text and query_text.strip():
            q = query_text.strip()
        elif req.categories:
            q = f"top attractions {' '.join(req.categories)}"
        else:
            q = "top attractions"

        # Zoom level approximation from radius in meters
        zoom = 14
        if req.radius_m <= 2000:
            zoom = 15
        elif req.radius_m >= 30000:
            zoom = 11
        elif req.radius_m >= 15000:
            zoom = 12

        return {
            "engine": "google_maps",
            "type": "search",
            "q": q,
            "ll": f"@{req.center.lat},{req.center.lon},{zoom}z",
            "hl": "en",
        }

    @staticmethod
    def build_places_params(req: PlacesSearchRequest, query_text: str | None = None) -> dict[str, Any]:
        """Alias for compatibility with coordinator places parameter extraction."""
        return SerpApiMapsAdapter.build_params(req, query_text=query_text)

    async def search_places(
        self,
        req: PlacesSearchRequest,
        authorizer: SearchAuthorizer,
        *,
        query_text: str | None = None,
    ) -> SearchResult[Place]:
        """Execute a Google Maps attraction search via SerpApi."""
        api_key = get_serpapi_key(self._settings, provider=PROVIDER, capability=Capability.PLACES)
        params = self.build_params(req, query_text=query_text)
        authorizer.authorize(Capability.PLACES, search_fingerprint=fingerprint(PROVIDER, params))
        payload = await self._http.request_json(
            "GET",
            BASE_URL,
            capability=Capability.PLACES,
            secrets=[api_key],
            params={**params, "api_key": api_key},
        )
        return self.parse_response(payload, params, retrieved_at=utcnow(), center=req.center)

    @staticmethod
    def parse_response(
        payload: Any,
        params: dict[str, Any],
        *,
        retrieved_at: datetime,
        center: Coordinate | None = None,
    ) -> SearchResult[Place]:
        """Parse SerpApi Google Maps response into normalized Place models."""
        has_results = check_serpapi_payload(payload, provider=PROVIDER, capability=Capability.PLACES)
        payload_dict = as_dict(payload)
        meta_in = as_dict(payload_dict.get("search_metadata"))
        search_id = as_str(meta_in.get("id"))

        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.PLACES,
            retrieved_at=retrieved_at,
            request_params=params,
            provider_search_id=search_id,
            limitations=[
                "Attractions are sourced from SerpApi Google Maps engine.",
                "Ratings, review counts, and operating hours reflect Google Maps listings.",
            ],
        )

        if not has_results:
            return SearchResult(status="empty", items=[], meta=meta)

        raw_results = payload_dict.get("local_results")
        if raw_results is None or not isinstance(raw_results, list):
            raise ProviderResponseError(
                f"{PROVIDER} returned an unexpected response shape: missing local_results.",
                provider=PROVIDER,
                capability=Capability.PLACES,
            )

        places: list[Place] = []
        skipped = 0
        seen_place_ids: set[str] = set()
        seen_signatures: set[tuple[str, float, float]] = set()

        for raw_item in raw_results:
            parsed = _parse_local_result(raw_item, retrieved_at, search_id, center)
            if parsed is None:
                skipped += 1
                continue

            # Deduplication: check place_id or name+coordinate
            if parsed.place_id and parsed.place_id in seen_place_ids:
                continue

            sig = (
                (parsed.name or "").lower().strip(),
                round(parsed.coordinate.lat, 3),
                round(parsed.coordinate.lon, 3),
            )
            if sig in seen_signatures:
                continue

            if parsed.place_id:
                seen_place_ids.add(parsed.place_id)
            seen_signatures.add(sig)
            places.append(parsed)

        if skipped:
            meta.warnings.append(f"Skipped {skipped} attraction(s) without usable names or coordinates.")

        return SearchResult(status="ok" if places else "empty", items=places, meta=meta)

    # ---- Geocoding --------------------------------------------------------------------
    @staticmethod
    def build_geocode_params(req: GeocodeRequest) -> dict[str, Any]:
        """Build parameters for geocoding a location string via Google Maps."""
        return {
            "engine": "google_maps",
            "type": "search",
            "q": req.text,
            "hl": "en",
        }

    async def geocode(
        self, req: GeocodeRequest, authorizer: SearchAuthorizer
    ) -> SearchResult[GeocodeResult]:
        """Geocode a location query via SerpApi Google Maps."""
        api_key = get_serpapi_key(self._settings, provider=PROVIDER, capability=Capability.GEOCODING)
        params = self.build_geocode_params(req)
        authorizer.authorize(Capability.GEOCODING, search_fingerprint=fingerprint(PROVIDER, params))
        payload = await self._http.request_json(
            "GET",
            BASE_URL,
            capability=Capability.GEOCODING,
            secrets=[api_key],
            params={**params, "api_key": api_key},
        )
        return self.parse_geocode(payload, params, retrieved_at=utcnow())

    @staticmethod
    def parse_geocode(
        payload: Any, params: dict[str, Any], *, retrieved_at: datetime
    ) -> SearchResult[GeocodeResult]:
        """Parse Google Maps geocoding response into GeocodeResult models."""
        has_results = check_serpapi_payload(payload, provider=PROVIDER, capability=Capability.GEOCODING)
        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.GEOCODING,
            retrieved_at=retrieved_at,
            request_params=params,
        )
        if not has_results:
            return SearchResult(status="empty", items=[], meta=meta)

        payload_dict = as_dict(payload)
        candidates: list[dict[str, Any]] = []
        if isinstance(payload_dict.get("place_results"), dict):
            candidates.append(payload_dict["place_results"])
        if isinstance(payload_dict.get("local_results"), list):
            candidates.extend(payload_dict["local_results"])

        results: list[GeocodeResult] = []
        for cand in candidates:
            d = as_dict(cand)
            gps = as_dict(d.get("gps_coordinates"))
            lat = as_float(gps.get("latitude"))
            lon = as_float(gps.get("longitude"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            title = as_str(d.get("title"))
            address = as_str(d.get("address"))
            formatted = f"{title}, {address}" if title and address else (title or address)
            pid = as_str(d.get("place_id")) or as_str(d.get("data_id"))
            results.append(
                GeocodeResult(
                    formatted=formatted,
                    coordinate=Coordinate(lat=lat, lon=lon),
                    result_type=as_str(d.get("type")),
                    provenance=Provenance(
                        provider=PROVIDER,
                        capability=Capability.GEOCODING,
                        retrieved_at=retrieved_at,
                        provider_id=pid,
                        raw=d,
                    ),
                )
            )
            if len(results) >= 1:
                break

        return SearchResult(status="ok" if results else "empty", items=results, meta=meta)


def _parse_local_result(
    raw: Any,
    retrieved_at: datetime,
    search_id: str | None,
    center: Coordinate | None,
) -> Place | None:
    """Parse a single Google Maps local result entry into Place domain model."""
    d = as_dict(raw)
    if not d:
        return None

    name = as_str(d.get("title"))
    if not name or not name.strip():
        return None

    gps = as_dict(d.get("gps_coordinates"))
    lat = as_float(gps.get("latitude"))
    lon = as_float(gps.get("longitude"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    coord = Coordinate(lat=lat, lon=lon)

    place_id = as_str(d.get("place_id")) or as_str(d.get("data_id"))
    rating = as_float(d.get("rating"))
    reviews_count = as_int(d.get("reviews"))
    address = as_str(d.get("address"))
    website = as_str(d.get("website"))
    phone = as_str(d.get("phone"))

    # Extract hours/operating schedule
    hours = as_str(d.get("hours")) or as_str(d.get("open_state"))
    if not hours and isinstance(d.get("operating_hours"), dict):
        op_hours = d["operating_hours"]
        # Format compact operating hours summary
        hours = "; ".join(f"{k}: {v}" for k, v in op_hours.items() if isinstance(v, str))

    # Categories: prefer types array, else single type string
    categories: list[str] = [t for t in as_list(d.get("types")) if isinstance(t, str)]
    if not categories:
        single_type = as_str(d.get("type"))
        if single_type:
            categories = [single_type]

    # Calculate distance from search center if available
    distance_m = None
    if center is not None:
        distance_m = _haversine_distance_m(center.lat, center.lon, lat, lon)

    # Missing fields list
    missing_fields = [
        label
        for label, val in [
            ("address", address),
            ("rating", rating),
            ("opening_hours", hours),
            ("website", website),
            ("phone", phone),
        ]
        if val is None
    ]

    desc = as_str(d.get("description")) or as_str(d.get("snippet"))

    return Place(
        place_id=place_id,
        name=name.strip(),
        categories=categories,
        address=address,
        coordinate=coord,
        distance_from_center_m=distance_m,
        opening_hours=hours,
        website=website,
        phone=phone,
        rating=rating,
        reviews_count=reviews_count,
        description=desc,
        missing_fields=missing_fields,
        provenance=Provenance(
            provider=PROVIDER,
            capability=Capability.PLACES,
            retrieved_at=retrieved_at,
            provider_id=place_id,
            source_url=as_str(d.get("reviews_link")) or as_str(d.get("place_id_search")),
            search_id=search_id,
            raw={k: v for k, v in d.items() if k not in _RAW_DROP},
        ),
    )
