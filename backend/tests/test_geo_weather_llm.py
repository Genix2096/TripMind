from datetime import UTC, date, datetime

import pytest
from pydantic import BaseModel

from app.core.errors import (
    LLMOutputError,
    MissingCredentialsError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from app.models.common import Coordinate
from app.models.geo import GeocodeRequest, PlacesSearchRequest, RouteRequest
from app.planning.weather_coverage import Coverage, assess_dates
from app.providers.geoapify.places import GeoapifyPlacesAdapter
from app.providers.geoapify.routing import GeoapifyRoutingAdapter
from app.providers.groq.client import GroqLLMClient
from app.providers.openweather.adapter import OpenWeatherAdapter
from tests import fixtures
from tests.conftest import NOW, json_transport

C = Coordinate(lat=15.4, lon=73.8)
PLACES_REQ = PlacesSearchRequest(categories=["tourism.sights", "beach"], center=C, radius_m=5000, limit=10)
ROUTE_REQ = RouteRequest(waypoints=[C, Coordinate(lat=15.5, lon=73.9)], mode="drive")


# ---------------- Geoapify places / geocode -------------------------------------------------


async def test_places_params_and_parsing(settings, authorizer):
    t = json_transport(fixtures.PLACES_OK)
    result = await GeoapifyPlacesAdapter(settings, transport=t.build()).search_places(PLACES_REQ, authorizer)
    q = dict(t.requests[0].url.params)
    assert q["categories"] == "tourism.sights,beach"
    assert q["filter"] == "circle:73.8,15.4,5000" and q["bias"] == "proximity:73.8,15.4"
    assert q["apiKey"] == "test-geo-key-456"

    assert len(result.items) == 2 and any("Skipped 1" in w for w in result.meta.warnings)
    fort, nameless = result.items
    assert fort.name == "Test Fort" and fort.opening_hours == "Mo-Su 09:00-17:00"
    assert fort.website == "https://example.test/fort" and fort.provenance.provider_id == "pid1"
    assert nameless.name is None and "name" in nameless.missing_fields
    assert nameless.opening_hours is None and "opening_hours" in nameless.missing_fields


async def test_places_empty_and_bad_shape(settings, authorizer):
    r = GeoapifyPlacesAdapter.parse_places({"features": []}, {}, retrieved_at=NOW)
    assert r.status == "empty"
    with pytest.raises(ProviderResponseError):
        GeoapifyPlacesAdapter.parse_places({"unexpected": 1}, {}, retrieved_at=NOW)


async def test_geocode_parsing(settings, authorizer):
    t = json_transport(fixtures.GEOCODE_OK)
    result = await GeoapifyPlacesAdapter(settings, transport=t.build()).geocode(
        GeocodeRequest(text="Goa"), authorizer
    )
    assert dict(t.requests[0].url.params)["format"] == "json"
    g = result.items[0]
    assert g.coordinate.lat == 15.49 and g.confidence == 0.9 and g.provenance.provider_id == "g1"


async def test_geoapify_missing_key(empty_settings, authorizer):
    t = json_transport({})
    with pytest.raises(MissingCredentialsError) as e:
        await GeoapifyPlacesAdapter(empty_settings, transport=t.build()).search_places(PLACES_REQ, authorizer)
    assert e.value.details["env_var"] == "GEOAPIFY_API_KEY" and t.requests == []


async def test_geoapify_quota_error_not_retried(settings, authorizer):
    t = json_transport({"message": "quota"}, status=429)
    with pytest.raises(ProviderRateLimitError):
        await GeoapifyPlacesAdapter(settings, transport=t.build()).search_places(PLACES_REQ, authorizer)
    assert len(t.requests) == 1


# ---------------- Geoapify routing --------------------------------------------------------


async def test_routing_params_and_parsing(settings, authorizer):
    t = json_transport(fixtures.ROUTE_OK)
    result = await GeoapifyRoutingAdapter(settings, transport=t.build()).route(ROUTE_REQ, authorizer)
    q = dict(t.requests[0].url.params)
    assert q["waypoints"] == "15.4,73.8|15.5,73.9" and q["mode"] == "drive"
    route = result.items[0]
    assert route.distance_m == 12000 and route.duration_s == 1500
    assert route.geometry == [[[73.8, 15.4], [73.9, 15.5]]]  # malformed point dropped
    assert route.mode == "drive" and route.legs[0].duration_s == 1500


def test_routing_no_route_is_empty():
    r = GeoapifyRoutingAdapter.parse_response({"features": []}, ROUTE_REQ, {}, retrieved_at=NOW)
    assert r.status == "empty"


# ---------------- OpenWeather -------------------------------------------------------------


async def test_current_weather(settings, authorizer):
    t = json_transport(fixtures.CURRENT_OK)
    w = await OpenWeatherAdapter(settings, transport=t.build()).get_current(C, authorizer)
    q = dict(t.requests[0].url.params)
    assert q["appid"] == "test-ow-key-789" and q["units"] == "metric" and "_kind" not in q
    assert w.temp_c == 29.5 and w.condition == "Clouds" and w.rain_1h_mm is None
    assert w.provenance.provider == "openweather"


async def test_forecast_parsing_and_missing_key(settings, empty_settings, authorizer):
    start = int(datetime(2026, 10, 10, 0, 0, tzinfo=UTC).timestamp())
    t = json_transport(fixtures.forecast_payload(start, 4))
    f = await OpenWeatherAdapter(settings, transport=t.build()).get_forecast(C, authorizer)
    assert f.status == "ok" and len(f.entries) == 4 and f.timezone_offset_seconds == 19800
    assert f.entries[0].precipitation_probability == 0.4 and f.entries[0].rain_3h_mm == 1.2
    with pytest.raises(MissingCredentialsError):
        await OpenWeatherAdapter(empty_settings, transport=t.build()).get_forecast(C, authorizer)


async def test_forecast_and_current_calls_are_distinct_searches(settings):
    from app.core.authorization import SearchAuthorizer
    from app.models.common import Capability

    auth = SearchAuthorizer(run_id="r", limits={Capability.WEATHER: 2})
    t = json_transport(fixtures.CURRENT_OK)
    await OpenWeatherAdapter(settings, transport=t.build()).get_current(C, auth)
    t2 = json_transport(fixtures.forecast_payload(1790000000, 1))
    await OpenWeatherAdapter(settings, transport=t2.build()).get_forecast(C, auth)
    assert auth.usage() == {"weather": 2}


def test_weather_date_coverage():
    start = int(datetime(2026, 10, 10, 0, 0, tzinfo=UTC).timestamp())  # 05:30 IST start
    forecast = OpenWeatherAdapter.parse_forecast(
        fixtures.forecast_payload(start, 40), C, retrieved_at=NOW
    )
    days = assess_dates(forecast, [date(2026, 10, 11), date(2026, 10, 20), date(2026, 10, 1)])
    by_date = {d.date: d for d in days}
    assert by_date[date(2026, 10, 11)].coverage == Coverage.AVAILABLE
    assert by_date[date(2026, 10, 11)].max_precipitation_probability == 0.4
    far = by_date[date(2026, 10, 20)]
    assert far.coverage == Coverage.BEYOND_FORECAST_HORIZON and far.entries == [] and far.temp_max_c is None
    assert by_date[date(2026, 10, 1)].coverage == Coverage.BEFORE_FORECAST_WINDOW


def test_weather_coverage_no_data_and_partial():
    empty = OpenWeatherAdapter.parse_forecast({"list": []}, C, retrieved_at=NOW)
    assert empty.status == "empty"
    assert assess_dates(empty, [date(2026, 10, 11)])[0].coverage == Coverage.NO_FORECAST_DATA
    start = int(datetime(2026, 10, 10, 0, 0, tzinfo=UTC).timestamp())
    partial = OpenWeatherAdapter.parse_forecast(fixtures.forecast_payload(start, 2), C, retrieved_at=NOW)
    assert assess_dates(partial, [date(2026, 10, 10)])[0].coverage == Coverage.PARTIAL


# ---------------- Groq --------------------------------------------------------------------


class Origin(BaseModel):
    origin: str | None = None


async def test_groq_requires_key_and_model(empty_settings, settings, authorizer):
    from app.core.config import Settings

    t = json_transport(fixtures.GROQ_OK)
    with pytest.raises(MissingCredentialsError):
        await GroqLLMClient(empty_settings, transport=t.build()).chat([{"role": "user", "content": "hi"}], authorizer)
    no_model = Settings(_env_file=None, groq_api_key="k")
    with pytest.raises(MissingCredentialsError) as e:
        await GroqLLMClient(no_model, transport=t.build()).chat([{"role": "user", "content": "hi"}], authorizer)
    assert e.value.details["env_var"] == "GROQ_MODEL" and t.requests == []


async def test_groq_chat_sends_configured_model_and_bearer(settings, authorizer):
    t = json_transport(fixtures.GROQ_OK)
    r = await GroqLLMClient(settings, transport=t.build()).chat([{"role": "user", "content": "hi"}], authorizer)
    req = t.requests[0]
    assert req.headers["authorization"] == "Bearer test-groq-key-abc"
    assert b'"model":"test-model"' in req.content.replace(b" ", b"")
    assert r.content and r.prompt_tokens == 10


async def test_groq_structured_output_valid_and_invalid(settings, authorizer):
    ok = await GroqLLMClient(settings, transport=json_transport(fixtures.GROQ_OK).build()).complete_structured(
        [{"role": "user", "content": "from MAA"}], Origin, authorizer
    )
    assert ok.origin == "MAA"
    bad_payload = {"choices": [{"message": {"content": "not json"}}]}
    t = json_transport(bad_payload)
    with pytest.raises(LLMOutputError):
        await GroqLLMClient(settings, transport=t.build()).complete_structured(
            [{"role": "user", "content": "x"}], Origin, authorizer
        )
    assert len(t.requests) == 1  # no retry on bad output


def test_groq_tool_calls_are_requests_only():
    r = GroqLLMClient.parse_response(fixtures.GROQ_TOOL)
    assert r.tool_calls[0].name == "search_flights" and r.tool_calls[0].arguments == {"a": 1}
    bad = {"choices": [{"message": {"tool_calls": [{"function": {"name": "x", "arguments": "[1]"}}]}}]}
    with pytest.raises(LLMOutputError):
        GroqLLMClient.parse_response(bad)
    with pytest.raises(ProviderResponseError):
        GroqLLMClient.parse_response({"choices": []})
