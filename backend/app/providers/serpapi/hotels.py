"""SerpApi Google Hotels adapter (engine=google_hotels).

Uses the same SerpApi credential as flights (via get_serpapi_key) but has its own request
building and parsing. Prices are copied exactly as returned: a nightly rate is never derived
from a total or vice versa.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.models.common import (
    Capability,
    Coordinate,
    Money,
    Provenance,
    SearchMeta,
    SearchResult,
)
from app.models.hotels import (
    HotelOption,
    HotelPrice,
    HotelPriceSource,
    HotelSearchRequest,
    HotelSort,
)
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

PROVIDER = "serpapi_google_hotels"
BASE_URL = "https://serpapi.com/search.json"

_SORT = {HotelSort.LOWEST_PRICE: 3, HotelSort.HIGHEST_RATING: 8, HotelSort.MOST_REVIEWED: 13}
_RATING = {3.5: 7, 4.0: 8, 4.5: 9}
# Bulky provider fields dropped from the stored raw copy; the useful parts are normalized.
_RAW_DROP = {"images", "health_and_safety"}


class SerpApiHotelsAdapter(BaseAdapter):
    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)

    @staticmethod
    def build_params(req: HotelSearchRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "engine": "google_hotels",
            "q": req.query,
            "check_in_date": req.check_in.isoformat(),
            "check_out_date": req.check_out.isoformat(),
            "adults": req.adults,
            "currency": req.currency,
        }
        if req.children_ages:
            params["children"] = req.children
            params["children_ages"] = ",".join(str(a) for a in req.children_ages)
        if req.gl:
            params["gl"] = req.gl.lower()
        if req.hl:
            params["hl"] = req.hl
        if req.sort_by:
            params["sort_by"] = _SORT[req.sort_by]
        if req.min_price is not None:
            params["min_price"] = req.min_price
        if req.max_price is not None:
            params["max_price"] = req.max_price
        if req.min_rating is not None:
            params["rating"] = _RATING[req.min_rating]
        if req.hotel_classes:
            params["hotel_class"] = ",".join(str(c) for c in req.hotel_classes)
        if req.property_types:
            params["property_types"] = ",".join(str(c) for c in req.property_types)
        if req.amenities:
            params["amenities"] = ",".join(str(c) for c in req.amenities)
        if req.free_cancellation:
            params["free_cancellation"] = "true"
        if req.next_page_token:
            params["next_page_token"] = req.next_page_token
        return params

    async def search(
        self, req: HotelSearchRequest, authorizer: SearchAuthorizer
    ) -> SearchResult[HotelOption]:
        api_key = get_serpapi_key(self._settings, provider=PROVIDER, capability=Capability.HOTELS)
        params = self.build_params(req)
        authorizer.authorize(Capability.HOTELS, search_fingerprint=fingerprint(PROVIDER, params))
        payload = await self._http.request_json(
            "GET",
            BASE_URL,
            capability=Capability.HOTELS,
            secrets=[api_key],
            params={**params, "api_key": api_key},
        )
        return self.parse_response(payload, req, params, retrieved_at=utcnow())

    @staticmethod
    def parse_response(
        payload: Any,
        req: HotelSearchRequest,
        params: dict[str, Any],
        *,
        retrieved_at: datetime,
    ) -> SearchResult[HotelOption]:
        has_results = check_serpapi_payload(payload, provider=PROVIDER, capability=Capability.HOTELS)
        payload = as_dict(payload)
        meta_in = as_dict(payload.get("search_metadata"))
        search_id = as_str(meta_in.get("id"))
        currency = (as_str(as_dict(payload.get("search_parameters")).get("currency")) or req.currency).upper()
        pagination = as_dict(payload.get("serpapi_pagination"))

        limitations = [
            ("Hotel search results are not reservations and do not guarantee room availability "
            "or the final checkout price."),
            (f"Prices reflect the provider's search for {req.adults} adult(s) and {req.children} "
            f"child(ren) over {req.nights} night(s); the provider API has no room-count parameter."),
            "Cancellation terms are not included in list results.",
        ]
        if req.free_cancellation:
            limitations.append("Results were filtered by the provider using its free-cancellation filter.")
        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.HOTELS,
            retrieved_at=retrieved_at,
            request_params=params,
            provider_search_id=search_id,
            next_page_token=as_str(pagination.get("next_page_token")),
            limitations=limitations,
        )

        hotels: list[HotelOption] = []
        skipped = 0
        if has_results:
            for raw in as_list(payload.get("properties")):
                option = _parse_property(raw, len(hotels), currency, search_id, retrieved_at)
                if option is None:
                    skipped += 1
                    continue
                hotels.append(option)
        if skipped:
            meta.warnings.append(f"Skipped {skipped} malformed hotel entr{'y' if skipped == 1 else 'ies'}.")
        return SearchResult(status="ok" if hotels else "empty", items=hotels, meta=meta)


def _money(value: Any, currency: str) -> Money | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Money(amount=Decimal(str(value)), currency=currency)
    return None


def _price(raw: Any, currency: str) -> HotelPrice | None:
    d = as_dict(raw)
    if not d:
        return None
    price = HotelPrice(
        amount=_money(d.get("extracted_lowest"), currency),
        display_text=as_str(d.get("lowest")),
        before_taxes_fees=_money(d.get("extracted_before_taxes_fees"), currency),
    )
    if price.amount is None and price.display_text is None and price.before_taxes_fees is None:
        return None
    return price


def _parse_property(
    raw: Any, index: int, currency: str, search_id: str | None, retrieved_at: datetime
) -> HotelOption | None:
    d = as_dict(raw)
    name = as_str(d.get("name"))
    if not d or name is None:
        return None

    gps = as_dict(d.get("gps_coordinates"))
    lat, lon = as_float(gps.get("latitude")), as_float(gps.get("longitude"))
    coordinates = None
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
        coordinates = Coordinate(lat=lat, lon=lon)

    images: list[str] = []
    for img in as_list(d.get("images"))[:10]:
        im = as_dict(img)
        url = as_str(im.get("original_image")) or as_str(im.get("thumbnail"))
        if url:
            images.append(url)

    sources = []
    for s in as_list(d.get("prices")):
        sd = as_dict(s)
        nightly = as_dict(sd.get("rate_per_night"))
        sources.append(
            HotelPriceSource(
                source=as_str(sd.get("source")),
                nightly=_money(nightly.get("extracted_lowest"), currency),
                num_guests=as_int(sd.get("num_guests")),
            )
        )

    nightly_rate = _price(d.get("rate_per_night"), currency)
    total_rate = _price(d.get("total_rate"), currency)
    token = as_str(d.get("property_token"))
    rating = as_float(d.get("overall_rating"))

    missing = []
    if nightly_rate is None or nightly_rate.amount is None:
        missing.append("nightly_rate")
    if total_rate is None or total_rate.amount is None:
        missing.append("total_rate")
    if rating is None:
        missing.append("rating")
    if coordinates is None:
        missing.append("coordinates")
    missing.append("address")

    return HotelOption(
        hotel_id=f"hotel-{index}",
        name=name,
        property_type=as_str(d.get("type")),
        description=as_str(d.get("description")),
        coordinates=coordinates,
        hotel_class=as_int(d.get("extracted_hotel_class")),
        rating=rating,
        review_count=as_int(d.get("reviews")),
        location_rating=as_float(d.get("location_rating")),
        amenities=[a for a in as_list(d.get("amenities")) if isinstance(a, str)],
        excluded_amenities=[a for a in as_list(d.get("excluded_amenities")) if isinstance(a, str)],
        images=images,
        check_in_time=as_str(d.get("check_in_time")),
        check_out_time=as_str(d.get("check_out_time")),
        nightly_rate=nightly_rate,
        total_rate=total_rate,
        price_sources=sources,
        link=as_str(d.get("link")),
        property_token=token,
        missing_fields=missing,
        provenance=Provenance(
            provider=PROVIDER,
            capability=Capability.HOTELS,
            retrieved_at=retrieved_at,
            provider_id=token,
            source_url=as_str(d.get("link")),
            search_id=search_id,
            raw={k: v for k, v in d.items() if k not in _RAW_DROP},
        ),
    )
