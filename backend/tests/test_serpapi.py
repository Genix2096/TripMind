from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.core.authorization import SearchAuthorizer
from app.core.errors import (
    DuplicateSearchError,
    MissingCredentialsError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ToolAuthorizationError,
    ToolCallLimitExceeded,
)
from app.models.common import Capability, Coordinate
from app.models.flights import FlightSearchRequest, PriceScope
from app.models.geo import PlacesSearchRequest
from app.models.hotels import HotelSearchRequest
from app.providers.serpapi.flights import SerpApiFlightsAdapter
from app.providers.serpapi.hotels import SerpApiHotelsAdapter
from app.providers.serpapi.maps import SerpApiMapsAdapter
from tests import fixtures
from tests.conftest import RecordingTransport, json_transport

FLIGHT_REQ = FlightSearchRequest(
    origin="AAA", destination="BBB", outbound_date=date(2026, 12, 1),
    return_date=date(2026, 12, 5), currency="INR", adults=2,
)
HOTEL_REQ = HotelSearchRequest(
    query="hotels in Testville", check_in=date(2026, 12, 1), check_out=date(2026, 12, 5),
    currency="INR", adults=2, children_ages=[5],
)
PARIS_COORD = Coordinate(lat=48.8566, lon=2.3522)
MAPS_REQ = PlacesSearchRequest(
    categories=["sights", "museum"],
    center=PARIS_COORD,
    radius_m=10000,
)


def flights(settings, transport):
    return SerpApiFlightsAdapter(settings, transport=transport.build())


def hotels(settings, transport):
    return SerpApiHotelsAdapter(settings, transport=transport.build())


def maps(settings, transport):
    return SerpApiMapsAdapter(settings, transport=transport.build())


# ---------------- flights -----------------------------------------------------------------


async def test_flight_params_and_parsing(settings, authorizer):
    t = json_transport(fixtures.FLIGHTS_OK)
    result = await flights(settings, t).search(FLIGHT_REQ, authorizer)

    q = dict(t.requests[0].url.params)
    assert q["engine"] == "google_flights" and q["type"] == "1" and q["return_date"] == "2026-12-05"
    assert q["adults"] == "2" and q["currency"] == "INR" and q["api_key"] == "test-serp-key-123"
    assert len(t.requests) == 1

    assert result.status == "ok" and len(result.items) == 2  # 'garbage' and empty skipped
    assert "api_key" not in result.meta.request_params
    assert any("Skipped 2" in w for w in result.meta.warnings)
    best, other = result.items
    assert best.provider_ranked_best and not other.provider_ranked_best
    assert best.price.amount == Decimal(5400) and best.price.currency == "INR"
    assert best.price_scope == PriceScope.UNSPECIFIED
    assert best.stops == 0 and best.segments[0].flight_number == "TA 1"
    assert best.return_leg_details_pending is True
    assert best.provenance.provider == "serpapi_google_flights"
    assert best.provenance.search_id == "sm1" and best.provenance.source_url == "https://example.test/gf"
    assert best.provenance.raw["departure_token"] == "tok-out-1"
    assert result.meta.provider_extras["price_insights"]["lowest_price"] == 5000
    
def test_flight_deduplication_deterministic_secondary():
    import datetime

    from app.models.flights import FlightSearchRequest
    from app.providers.serpapi.flights import (
        SerpApiFlightsAdapter,
        _flight_signature,
        _parse_option,
    )

    req = FlightSearchRequest(origin="AAA", destination="BBB", outbound_date=datetime.date(2026, 12, 1), currency="INR")
    retrieved = datetime.datetime(2026, 10, 10, tzinfo=datetime.UTC)

    # Simulating a flight with the exact same segments, times, and prices but different departure tokens and formatting
    raw1 = {
        "flights": [{"airline": "TestAir", "flight_number": "TA 1", "departure_airport": {"id": "AAA", "time": "2026-12-01 10:00"}, "arrival_airport": {"id": "BBB", "time": "2026-12-01 12:00"}}],
        "price": 5400,
        "total_duration": 120,
        "booking_token": "token_1",
    }

    raw2 = {
        "flights": [{"airline": "testair ", "flight_number": "TA1", "departure_airport": {"id": "AAA", "time": "2026-12-01 10:00"}, "arrival_airport": {"id": "BBB", "time": "2026-12-01 12:00"}}],
        "price": 5400.0,
        "total_duration": 120,
        "booking_token": "token_2",
    }

    opt1 = _parse_option(raw1, 0, True, req, "INR", "sid", "url", retrieved)
    opt2 = _parse_option(raw2, 1, False, req, "INR", "sid", "url", retrieved)

    # Normalized signatures match despite whitespace/casing/token differences
    sig1 = _flight_signature(opt1)
    sig2 = _flight_signature(opt2)
    assert sig1 == sig2

    payload = {
        "search_metadata": {"id": "sid"},
        "best_flights": [raw1],
        "other_flights": [raw2],
    }
    result = SerpApiFlightsAdapter.parse_response(payload, req, {}, retrieved_at=retrieved)
    assert len(result.items) == 1
    assert result.items[0].provider_ranked_best is True


def test_flight_deduplication_across_best_and_other_with_distinct_flights():
    import datetime

    from app.models.flights import FlightSearchRequest
    from app.providers.serpapi.flights import SerpApiFlightsAdapter
    from tests.conftest import NOW
    from tests.fixtures import FLIGHTS_WITH_DUPLICATES

    req = FlightSearchRequest(origin="AAA", destination="BBB", outbound_date=datetime.date(2026, 12, 1), currency="INR")
    result = SerpApiFlightsAdapter.parse_response(FLIGHTS_WITH_DUPLICATES, req, {}, retrieved_at=NOW)

    # Total 7 raw flights: 1 duplicate should be dropped, leaving 6 distinct flights
    assert len(result.items) == 6

    # 1. Duplicate of Flight A was dropped, and the best_flights version was retained
    retained_a = [f for f in result.items if f.segments[0].airline == "TestAir" and f.segments[0].flight_number == "TA 1" and f.segments[0].departure.local_time == datetime.datetime(2026, 12, 1, 8, 0)]
    assert len(retained_a) == 1
    assert retained_a[0].provider_ranked_best is True

    # 2. Distinct departure time was not merged
    flight_c = [f for f in result.items if f.segments[0].airline == "TestAir" and f.segments[0].flight_number == "TA 1" and f.segments[0].departure.local_time == datetime.datetime(2026, 12, 1, 12, 0)]
    assert len(flight_c) == 1

    # 3. Distinct flight number was not merged
    flight_d = [f for f in result.items if f.segments[0].airline == "TestAir" and f.segments[0].flight_number == "TA 2"]
    assert len(flight_d) == 1

    # 4. Distinct price was not merged
    flight_e = [f for f in result.items if f.segments[0].airline == "SkyWay" and f.price.amount == 7000]
    flight_b = [f for f in result.items if f.segments[0].airline == "SkyWay" and f.price.amount == 6200]
    assert len(flight_e) == 1
    assert len(flight_b) == 1

    # 5. Distinct airline was not merged
    flight_f = [f for f in result.items if f.segments[0].airline == "AeroFly"]
    assert len(flight_f) == 1


async def test_flight_missing_fields_are_reported_not_filled(settings, authorizer):
    result = await flights(settings, json_transport(fixtures.FLIGHTS_OK)).search(FLIGHT_REQ, authorizer)
    other = result.items[1]
    assert other.price is None and "price" in other.missing_fields
    assert "segment_times" in other.missing_fields  # unparseable time stays None
    assert other.stops == 1 and other.layovers[0].duration_minutes == 60
    assert other.segments[1].arrival.local_time is None
    assert other.segments[1].flight_number is None


async def test_flight_no_results_is_empty_not_error(settings, authorizer):
    result = await flights(settings, json_transport(fixtures.NO_RESULTS)).search(FLIGHT_REQ, authorizer)
    assert result.status == "empty" and result.items == []


async def test_flight_one_way_params(settings, authorizer):
    t = json_transport(fixtures.NO_RESULTS)
    req = FlightSearchRequest(origin="AAA", destination="BBB", outbound_date=date(2026, 12, 1),
                              currency="INR", max_stops=1, max_duration_minutes=600)
    await flights(settings, t).search(req, authorizer)
    q = dict(t.requests[0].url.params)
    assert q["type"] == "2" and "return_date" not in q and q["stops"] == "2" and q["max_duration"] == "600"


# ---------------- hotels ------------------------------------------------------------------


async def test_hotel_params_and_parsing(settings, authorizer):
    t = json_transport(fixtures.HOTELS_OK)
    result = await hotels(settings, t).search(HOTEL_REQ, authorizer)
    q = dict(t.requests[0].url.params)
    assert q["engine"] == "google_hotels" and q["q"] == "hotels in Testville"
    assert q["check_in_date"] == "2026-12-01" and q["children"] == "1" and q["children_ages"] == "5"
    assert "rooms" not in q

    assert result.status == "ok" and len(result.items) == 2  # nameless skipped
    h = result.items[0]
    assert h.nightly_rate.amount.amount == Decimal(4000)
    assert h.nightly_rate.before_taxes_fees.amount == Decimal(3500)
    assert h.total_rate.amount.amount == Decimal(16000)
    assert h.rating == 4.3 and h.review_count == 250 and h.hotel_class == 4
    assert h.coordinates.lat == 15.5 and h.images == ["https://example.test/o.jpg"]
    assert h.link == "https://example.test/resort" and h.provenance.source_url == h.link
    assert h.provenance.provider_id == "ptok1" and "images" not in h.provenance.raw
    assert h.address is None and "address" in h.missing_fields
    assert result.meta.next_page_token == "next-1"
    assert any("not reservations" in l for l in result.meta.limitations)


async def test_hotel_display_only_price_is_not_parsed_into_amount(settings, authorizer):
    result = await hotels(settings, json_transport(fixtures.HOTELS_OK)).search(HOTEL_REQ, authorizer)
    inn = result.items[1]
    assert inn.nightly_rate.display_text == "₹2,000" and inn.nightly_rate.amount is None
    assert inn.total_rate is None  # never derived from nightly
    assert "total_rate" in inn.missing_fields and "nightly_rate" in inn.missing_fields


async def test_hotel_no_results_is_empty(settings, authorizer):
    result = await hotels(settings, json_transport(fixtures.HOTEL_NO_RESULTS)).search(HOTEL_REQ, authorizer)
    assert result.status == "empty"


# ---------------- shared SerpApi credential ------------------------------------------------


async def test_flights_and_hotels_and_maps_use_the_same_serpapi_key(settings, authorizer):
    tf, th, tm = json_transport(fixtures.NO_RESULTS), json_transport(fixtures.HOTEL_NO_RESULTS), json_transport(fixtures.GOOGLE_MAPS_NO_RESULTS)
    await flights(settings, tf).search(FLIGHT_REQ, authorizer)
    await hotels(settings, th).search(HOTEL_REQ, authorizer)
    await maps(settings, tm).search_places(MAPS_REQ, authorizer)
    assert tf.requests[0].url.params["api_key"] == th.requests[0].url.params["api_key"] == tm.requests[0].url.params["api_key"] == "test-serp-key-123"


async def test_one_missing_serpapi_key_disables_all_three(empty_settings, authorizer):
    t = json_transport({})
    for call in (
        lambda: flights(empty_settings, t).search(FLIGHT_REQ, authorizer),
        lambda: hotels(empty_settings, t).search(HOTEL_REQ, authorizer),
        lambda: maps(empty_settings, t).search_places(MAPS_REQ, authorizer),
    ):
        with pytest.raises(MissingCredentialsError) as exc:
            await call()
        assert exc.value.details["env_var"] == "SERPAPI_API_KEY"
    assert t.requests == []  # no request attempted
    assert authorizer.usage() == {}  # and no quota counted


# ---------------- failures: typed, no fallback, no retry -----------------------------------


@pytest.mark.parametrize(
    "status,exc",
    [(401, ProviderAuthError), (403, ProviderAuthError), (429, ProviderRateLimitError),
     (400, ProviderRequestError), (500, ProviderUnavailableError), (503, ProviderUnavailableError)],
)
async def test_http_failures_map_to_typed_errors_with_single_attempt(settings, authorizer, status, exc):
    t = json_transport({"error": "boom test-serp-key-123"}, status=status)
    with pytest.raises(exc) as info:
        await flights(settings, t).search(FLIGHT_REQ, authorizer)
    assert len(t.requests) == 1  # never retried
    assert info.value.provider == "serpapi_google_flights"
    assert info.value.capability == Capability.FLIGHTS
    assert "test-serp-key-123" not in info.value.message


async def test_timeout_is_reported_and_not_retried(settings, authorizer):
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)

    t = RecordingTransport(boom)
    with pytest.raises(ProviderTimeoutError):
        await hotels(settings, t).search(HOTEL_REQ, authorizer)
    assert len(t.requests) == 1


async def test_network_error_message_has_no_url_or_key(settings, authorizer):
    def boom(request):
        raise httpx.ConnectError(f"cannot connect {request.url}", request=request)

    with pytest.raises(ProviderUnavailableError) as info:
        await flights(settings, RecordingTransport(boom)).search(FLIGHT_REQ, authorizer)
    assert "test-serp-key-123" not in str(info.value) and "serpapi.com" not in info.value.message


async def test_200_with_error_body_is_an_error_not_empty(settings, authorizer):
    with pytest.raises(ProviderRequestError) as info:
        await flights(settings, json_transport(fixtures.PROVIDER_ERROR)).search(FLIGHT_REQ, authorizer)
    assert info.value.code == "provider_invalid_request"


async def test_failed_search_never_yields_results(settings, authorizer):
    result = None
    try:
        result = await hotels(settings, json_transport({"error": "x"}, 500)).search(HOTEL_REQ, authorizer)
    except ProviderUnavailableError:
        pass
    assert result is None


# ---------------- authorization / bounded calls -------------------------------------------


async def test_identical_search_is_blocked_within_a_run(settings):
    auth = SearchAuthorizer(run_id="r", limits={Capability.FLIGHTS: 5})
    t = json_transport(fixtures.NO_RESULTS)
    adapter = flights(settings, t)
    await adapter.search(FLIGHT_REQ, auth)
    with pytest.raises(DuplicateSearchError):
        await adapter.search(FLIGHT_REQ, auth)
    assert len(t.requests) == 1


async def test_call_limit_is_enforced(settings):
    auth = SearchAuthorizer(run_id="r", limits={Capability.FLIGHTS: 1})
    t = json_transport(fixtures.NO_RESULTS)
    adapter = flights(settings, t)
    await adapter.search(FLIGHT_REQ, auth)
    other = FLIGHT_REQ.model_copy(update={"outbound_date": date(2026, 12, 2)})
    with pytest.raises(ToolCallLimitExceeded):
        await adapter.search(other, auth)
    assert len(t.requests) == 1


async def test_zero_limit_and_closed_run_block_calls(settings):
    t = json_transport(fixtures.NO_RESULTS)
    with pytest.raises(ToolCallLimitExceeded):
        await flights(settings, t).search(FLIGHT_REQ, SearchAuthorizer(run_id="r", limits={}))
    closed = SearchAuthorizer(run_id="r", limits={Capability.FLIGHTS: 3})
    closed.close()
    with pytest.raises(ToolAuthorizationError):
        await flights(settings, t).search(FLIGHT_REQ, closed)
    assert t.requests == []


async def test_authorizers_do_not_share_state(settings):
    a = SearchAuthorizer(run_id="a", limits={Capability.FLIGHTS: 1})
    b = SearchAuthorizer(run_id="b", limits={Capability.FLIGHTS: 1})
    adapter = flights(settings, json_transport(fixtures.NO_RESULTS))
    await adapter.search(FLIGHT_REQ, a)
    await adapter.search(FLIGHT_REQ, b)  # separate run: allowed
    assert a.usage() == b.usage() == {"flights": 1}


# ---------------- Google Maps (Places) ---------------------------------------------------


async def test_maps_params_and_parsing(settings, authorizer):
    t = json_transport(fixtures.GOOGLE_MAPS_OK)
    adapter = maps(settings, t)
    result = await adapter.search_places(MAPS_REQ, authorizer)

    # Verify HTTP request construction
    assert len(t.requests) == 1
    q = dict(t.requests[0].url.params)
    assert q["engine"] == "google_maps"
    assert q["type"] == "search"
    assert q["q"] == "top attractions sights museum"
    assert q["ll"] == "@48.8566,2.3522,14z"
    assert q["hl"] == "en"
    assert q["api_key"] == "test-serp-key-123"

    # api_key is scrubbed from SearchMeta
    assert "api_key" not in result.meta.request_params
    assert result.status == "ok"
    assert len(result.items) == 2  # 1 duplicate + 2 invalid entries skipped

    # Verify warning on skipped invalid entries
    assert any("Skipped 2" in w for w in result.meta.warnings)

    eiffel, louvre = result.items

    # Verify Eiffel Tower normalization
    assert eiffel.name == "Eiffel Tower"
    assert eiffel.place_id == "ChIJLU7jZClu5kcR4PcOOO6pNm0"
    assert eiffel.rating == 4.7
    assert eiffel.reviews_count == 350000
    assert eiffel.categories == ["Monument", "Tourist attraction"]
    assert "Champ de Mars" in (eiffel.address or "")
    assert eiffel.coordinate.lat == 48.8584
    assert eiffel.coordinate.lon == 2.2945
    assert eiffel.distance_from_center_m is not None and eiffel.distance_from_center_m > 0
    assert eiffel.opening_hours == "Open ⋅ Closes 11:45 PM"
    assert eiffel.website == "https://www.toureiffel.paris/en"
    assert eiffel.phone == "+33 892 70 12 39"
    assert eiffel.provenance.provider == "serpapi_google_maps"
    assert eiffel.provenance.provider_id == "ChIJLU7jZClu5kcR4PcOOO6pNm0"
    assert eiffel.provenance.search_id == "maps_meta_1"
    assert eiffel.provenance.source_url == "https://example.test/reviews/eiffel"

    # Verify Louvre Museum normalization
    assert louvre.name == "Louvre Museum"
    assert louvre.place_id == "ChIJD7fiBh9u5kcRYJSMaMOCCwQ"
    assert louvre.rating == 4.8
    assert louvre.reviews_count == 280000
    assert louvre.categories == ["Art museum"]
    assert louvre.opening_hours == "Open ⋅ Closes 6:00 PM"


async def test_maps_deduplication_by_name_and_coord(settings, authorizer):
    t = json_transport(fixtures.GOOGLE_MAPS_DUPLICATES)
    adapter = maps(settings, t)
    result = await adapter.search_places(MAPS_REQ, authorizer)

    assert result.status == "ok"
    # Even without place_id, identical normalized name and coords are deduplicated
    assert len(result.items) == 1
    assert result.items[0].name == "Central Park"


async def test_maps_no_results_and_empty(settings, authorizer):
    t_empty = json_transport(fixtures.GOOGLE_MAPS_EMPTY)
    res_empty = await maps(settings, t_empty).search_places(MAPS_REQ, authorizer)
    assert res_empty.status == "empty"
    assert res_empty.items == []

    auth2 = SearchAuthorizer(run_id="run_2", limits={Capability.PLACES: 4})
    t_no_res = json_transport(fixtures.GOOGLE_MAPS_NO_RESULTS)
    res_no_res = await maps(settings, t_no_res).search_places(MAPS_REQ, auth2)
    assert res_no_res.status == "empty"
    assert res_no_res.items == []


async def test_maps_bad_shape_raises(settings, authorizer):
    t = json_transport(fixtures.GOOGLE_MAPS_BAD_SHAPE)
    adapter = maps(settings, t)
    from app.core.errors import ProviderResponseError
    with pytest.raises(ProviderResponseError):
        await adapter.search_places(MAPS_REQ, authorizer)


async def test_maps_missing_key_raises(empty_settings, authorizer):
    t = json_transport({})
    adapter = maps(empty_settings, t)
    with pytest.raises(MissingCredentialsError) as exc_info:
        await adapter.search_places(MAPS_REQ, authorizer)
    assert exc_info.value.details["env_var"] == "SERPAPI_API_KEY"
    assert exc_info.value.provider == "serpapi_google_maps"


async def test_maps_query_text_override(settings, authorizer):
    t = json_transport(fixtures.GOOGLE_MAPS_OK)
    adapter = maps(settings, t)
    await adapter.search_places(MAPS_REQ, authorizer, query_text="historic sights in central Paris")
    q = dict(t.requests[0].url.params)
    assert q["q"] == "historic sights in central Paris"

