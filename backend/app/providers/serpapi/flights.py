"""SerpApi Google Flights adapter (engine=google_flights).

Parsing is flight-specific and must not be shared with the hotels adapter.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.models.common import Capability, Money, Provenance, SearchMeta, SearchResult
from app.models.flights import (
    Airport,
    FlightOption,
    FlightSearchRequest,
    FlightSegment,
    Layover,
    PriceScope,
    TravelClass,
)
from app.providers.base import (
    BaseAdapter,
    as_dict,
    as_int,
    as_list,
    as_str,
    utcnow,
)
from app.providers.serpapi.common import check_serpapi_payload, get_serpapi_key

PROVIDER = "serpapi_google_flights"
BASE_URL = "https://serpapi.com/search.json"

_TRAVEL_CLASS = {
    TravelClass.ECONOMY: 1,
    TravelClass.PREMIUM_ECONOMY: 2,
    TravelClass.BUSINESS: 3,
    TravelClass.FIRST: 4,
}
# SerpApi `stops`: 0 any, 1 nonstop, 2 <=1 stop, 3 <=2 stops
_STOPS = {0: 1, 1: 2, 2: 3}


def _normalize_string(val: str | None) -> str:
    if not val:
        return ""
    return re.sub(r"\s+", " ", val).strip().lower()


def _normalize_flight_number(val: str | None) -> str:
    if not val:
        return "none"
    return re.sub(r"\s+", "", val).upper()


def _flight_signature(option: FlightOption) -> str:
    parts = []
    for s in option.segments:
        airline = _normalize_string(s.airline)
        flight_num = _normalize_flight_number(s.flight_number)
        dep_code = _normalize_string(s.departure.code).upper()
        arr_code = _normalize_string(s.arrival.code).upper()
        dep_time = s.departure.local_time.strftime("%Y-%m-%dT%H:%M") if s.departure.local_time else "notime"
        arr_time = s.arrival.local_time.strftime("%Y-%m-%dT%H:%M") if s.arrival.local_time else "notime"
        parts.append(f"{airline}_{flight_num}_{dep_code}_{arr_code}_{dep_time}_{arr_time}")

    segment_sig = "|".join(parts)

    if option.price and option.price.amount is not None:
        price_amt = f"{Decimal(str(option.price.amount)):.2f}"
        price_curr = option.price.currency.strip().upper()
        price_sig = f"{price_amt}_{price_curr}"
    else:
        price_sig = "noprice"

    return f"{segment_sig}#{price_sig}"


class SerpApiFlightsAdapter(BaseAdapter):
    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)

    @staticmethod
    def build_params(req: FlightSearchRequest) -> dict[str, Any]:
        """Provider query parameters WITHOUT the credential."""
        params: dict[str, Any] = {
            "engine": "google_flights",
            "departure_id": req.origin,
            "arrival_id": req.destination,
            "outbound_date": req.outbound_date.isoformat(),
            "type": 1 if req.return_date else 2,
            "travel_class": _TRAVEL_CLASS[req.travel_class],
            "adults": req.adults,
            "currency": req.currency,
        }
        if req.return_date:
            params["return_date"] = req.return_date.isoformat()
        if req.children:
            params["children"] = req.children
        if req.infants_in_seat:
            params["infants_in_seat"] = req.infants_in_seat
        if req.infants_on_lap:
            params["infants_on_lap"] = req.infants_on_lap
        if req.max_stops is not None:
            params["stops"] = _STOPS[req.max_stops]
        if req.max_duration_minutes is not None:
            params["max_duration"] = req.max_duration_minutes
        if req.include_airlines:
            params["include_airlines"] = ",".join(req.include_airlines)
        if req.exclude_airlines:
            params["exclude_airlines"] = ",".join(req.exclude_airlines)
        if req.gl:
            params["gl"] = req.gl.lower()
        if req.hl:
            params["hl"] = req.hl
        if req.departure_token:
            params["departure_token"] = req.departure_token
        return params

    async def search(
        self, req: FlightSearchRequest, authorizer: SearchAuthorizer
    ) -> SearchResult[FlightOption]:
        # 1. credentials (no quota used if missing)  2. authorization  3. exactly one request
        api_key = get_serpapi_key(self._settings, provider=PROVIDER, capability=Capability.FLIGHTS)
        params = self.build_params(req)
        authorizer.authorize(Capability.FLIGHTS, search_fingerprint=fingerprint(PROVIDER, params))
        payload = await self._http.request_json(
            "GET",
            BASE_URL,
            capability=Capability.FLIGHTS,
            secrets=[api_key],
            params={**params, "api_key": api_key},
        )
        return self.parse_response(payload, req, params, retrieved_at=utcnow())

    @staticmethod
    def parse_response(
        payload: Any,
        req: FlightSearchRequest,
        params: dict[str, Any],
        *,
        retrieved_at: datetime,
    ) -> SearchResult[FlightOption]:
        has_results = check_serpapi_payload(payload, provider=PROVIDER, capability=Capability.FLIGHTS)
        payload = as_dict(payload)
        meta_in = as_dict(payload.get("search_metadata"))
        search_id = as_str(meta_in.get("id"))
        search_url = as_str(meta_in.get("google_flights_url"))
        currency = (as_str(as_dict(payload.get("search_parameters")).get("currency")) or req.currency).upper()

        limitations = [
            "Prices are provider search results, not guaranteed fares or confirmed availability.",
            "The provider does not state whether a price covers one traveler or all travelers.",
        ]
        if req.return_date and not req.departure_token:
            limitations.append(
                "Round-trip results describe the outbound leg with the round-trip price; "
                "return-leg details require a separate explicit search."
            )
        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.FLIGHTS,
            retrieved_at=retrieved_at,
            request_params=params,
            provider_search_id=search_id,
            provider_search_url=search_url,
            limitations=limitations,
            provider_extras={"price_insights": payload["price_insights"]}
            if isinstance(payload.get("price_insights"), dict)
            else {},
        )

        options: list[FlightOption] = []
        seen = set()
        seen_tokens = set()
        skipped = 0
        if has_results:
            n = 0
            for group, is_best in (("best_flights", True), ("other_flights", False)):
                for raw in as_list(payload.get(group)):
                    option = _parse_option(
                        raw, n, is_best, req, currency, search_id, search_url, retrieved_at
                    )
                    if option is None:
                        skipped += 1
                        continue

                    # Deduplicate based on deterministic normalized signature or provider tokens
                    sig = _flight_signature(option)
                    stable_token = option.booking_token

                    if sig in seen or (stable_token and stable_token in seen_tokens):
                        continue
                    seen.add(sig)
                    if stable_token:
                        seen_tokens.add(stable_token)

                    options.append(option)
                    n += 1
        if skipped:
            meta.warnings.append(f"Skipped {skipped} malformed flight entr{'y' if skipped == 1 else 'ies'}.")
        return SearchResult(status="ok" if options else "empty", items=options, meta=meta)


def _parse_time(value: Any) -> datetime | None:
    s = as_str(value)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _parse_airport(raw: Any) -> Airport:
    d = as_dict(raw)
    return Airport(name=as_str(d.get("name")), code=as_str(d.get("id")), local_time=_parse_time(d.get("time")))


def _parse_segment(raw: Any) -> FlightSegment | None:
    d = as_dict(raw)
    if not d:
        return None
    overnight = d.get("overnight")
    return FlightSegment(
        airline=as_str(d.get("airline")),
        flight_number=as_str(d.get("flight_number")),
        aircraft=as_str(d.get("airplane")),
        travel_class=as_str(d.get("travel_class")),
        departure=_parse_airport(d.get("departure_airport")),
        arrival=_parse_airport(d.get("arrival_airport")),
        duration_minutes=as_int(d.get("duration")),
        overnight=overnight if isinstance(overnight, bool) else None,
        legroom=as_str(d.get("legroom")),
        extensions=[e for e in as_list(d.get("extensions")) if isinstance(e, str)],
    )


def _parse_option(
    raw: Any,
    index: int,
    is_best: bool,
    req: FlightSearchRequest,
    currency: str,
    search_id: str | None,
    search_url: str | None,
    retrieved_at: datetime,
) -> FlightOption | None:
    d = as_dict(raw)
    segments = [s for s in (_parse_segment(x) for x in as_list(d.get("flights"))) if s]
    if not segments:
        return None

    layovers = []
    for x in as_list(d.get("layovers")):
        ld = as_dict(x)
        overnight = ld.get("overnight")
        layovers.append(
            Layover(
                airport_name=as_str(ld.get("name")),
                airport_code=as_str(ld.get("id")),
                duration_minutes=as_int(ld.get("duration")),
                overnight=overnight if isinstance(overnight, bool) else None,
            )
        )

    price_raw = d.get("price")
    price = None
    if isinstance(price_raw, (int, float)) and not isinstance(price_raw, bool):
        price = Money(amount=Decimal(str(price_raw)), currency=currency)

    emissions = as_dict(d.get("carbon_emissions"))
    grams = as_int(emissions.get("this_flight"))
    token = as_str(d.get("departure_token"))
    booking = as_str(d.get("booking_token"))
    trip_type = as_str(d.get("type"))

    missing = []
    if price is None:
        missing.append("price")
    if as_int(d.get("total_duration")) is None:
        missing.append("total_duration")
    if any(s.departure.local_time is None or s.arrival.local_time is None for s in segments):
        missing.append("segment_times")
    if any(s.airline is None for s in segments):
        missing.append("airline")

    return FlightOption(
        option_id=f"flight-{index}",
        segments=segments,
        layovers=layovers,
        total_duration_minutes=as_int(d.get("total_duration")),
        stops=len(segments) - 1,
        price=price,
        price_scope=PriceScope.UNSPECIFIED,
        trip_type=trip_type,
        provider_ranked_best=is_best,
        return_leg_details_pending=bool(req.return_date and not req.departure_token and token),
        departure_token=token,
        booking_token=booking,
        airline_logo=as_str(d.get("airline_logo")),
        carbon_emissions_grams=grams,
        missing_fields=missing,
        provenance=Provenance(
            provider=PROVIDER,
            capability=Capability.FLIGHTS,
            retrieved_at=retrieved_at,
            provider_id=booking or token,
            source_url=search_url,
            search_id=search_id,
            raw=d,
        ),
    )
