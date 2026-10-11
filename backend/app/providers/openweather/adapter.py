"""OpenWeather adapter (free-tier 2.5 endpoints: current weather and 5-day / 3-hour forecast).

Current conditions and forecasts are distinct types and distinct methods so one can never be
presented as the other. The forecast horizon is about 5 days from retrieval.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.core.errors import MissingCredentialsError, ProviderResponseError
from app.models.common import Capability, Coordinate, Provenance
from app.models.weather import CurrentWeather, ForecastEntry, WeatherForecast
from app.providers.base import (
    BaseAdapter,
    as_dict,
    as_float,
    as_int,
    as_list,
    as_str,
    utcnow,
)

PROVIDER = "openweather"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def _utc(ts: Any) -> datetime | None:
    n = as_float(ts)
    return datetime.fromtimestamp(n, tz=UTC) if n is not None else None


class OpenWeatherAdapter(BaseAdapter):
    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)

    def _key(self) -> str:
        key = self._settings.openweather_api_key
        if key is None:
            raise MissingCredentialsError(
                provider=PROVIDER, capability=Capability.WEATHER, env_var="OPENWEATHER_API_KEY"
            )
        return key.get_secret_value()

    @staticmethod
    def build_params(coord: Coordinate, kind: str) -> dict[str, Any]:
        return {"lat": coord.lat, "lon": coord.lon, "units": "metric", "_kind": kind}

    async def _fetch(self, url: str, coord: Coordinate, kind: str, authorizer: SearchAuthorizer) -> Any:
        key = self._key()
        params = self.build_params(coord, kind)
        authorizer.authorize(Capability.WEATHER, search_fingerprint=fingerprint(PROVIDER, params))
        send = {k: v for k, v in params.items() if not k.startswith("_")}
        return await self._http.request_json(
            "GET",
            url,
            capability=Capability.WEATHER,
            secrets=[key],
            params={**send, "appid": key},
        )

    async def get_current(self, coord: Coordinate, authorizer: SearchAuthorizer) -> CurrentWeather:
        payload = await self._fetch(CURRENT_URL, coord, "current", authorizer)
        return self.parse_current(payload, coord, retrieved_at=utcnow())

    async def get_forecast(self, coord: Coordinate, authorizer: SearchAuthorizer) -> WeatherForecast:
        payload = await self._fetch(FORECAST_URL, coord, "forecast", authorizer)
        return self.parse_forecast(payload, coord, retrieved_at=utcnow())

    @staticmethod
    def parse_current(payload: Any, coord: Coordinate, *, retrieved_at: datetime) -> CurrentWeather:
        if not isinstance(payload, dict) or "main" not in payload:
            raise ProviderResponseError(
                f"{PROVIDER} returned an unexpected current-weather response.",
                provider=PROVIDER,
                capability=Capability.WEATHER,
            )
        main = as_dict(payload.get("main"))
        weather = as_dict(as_list(payload.get("weather"))[0]) if as_list(payload.get("weather")) else {}
        return CurrentWeather(
            observed_at=_utc(payload.get("dt")),
            location_name=as_str(payload.get("name")),
            coordinate=coord,
            temp_c=as_float(main.get("temp")),
            feels_like_c=as_float(main.get("feels_like")),
            humidity_pct=as_int(main.get("humidity")),
            condition=as_str(weather.get("main")),
            description=as_str(weather.get("description")),
            wind_speed_ms=as_float(as_dict(payload.get("wind")).get("speed")),
            clouds_pct=as_int(as_dict(payload.get("clouds")).get("all")),
            rain_1h_mm=as_float(as_dict(payload.get("rain")).get("1h")),
            provenance=Provenance(
                provider=PROVIDER,
                capability=Capability.WEATHER,
                retrieved_at=retrieved_at,
                provider_id=str(payload["id"]) if isinstance(payload.get("id"), int) else None,
                raw={k: payload[k] for k in ("main", "weather", "wind", "clouds", "rain", "dt") if k in payload},
            ),
        )

    @staticmethod
    def parse_forecast(payload: Any, coord: Coordinate, *, retrieved_at: datetime) -> WeatherForecast:
        if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
            raise ProviderResponseError(
                f"{PROVIDER} returned an unexpected forecast response.",
                provider=PROVIDER,
                capability=Capability.WEATHER,
            )
        entries: list[ForecastEntry] = []
        for raw in payload["list"]:
            d = as_dict(raw)
            when = _utc(d.get("dt"))
            if when is None:
                continue
            main = as_dict(d.get("main"))
            wlist = as_list(d.get("weather"))
            w = as_dict(wlist[0]) if wlist else {}
            pop = as_float(d.get("pop"))
            entries.append(
                ForecastEntry(
                    forecast_time=when,
                    temp_c=as_float(main.get("temp")),
                    feels_like_c=as_float(main.get("feels_like")),
                    temp_min_c=as_float(main.get("temp_min")),
                    temp_max_c=as_float(main.get("temp_max")),
                    humidity_pct=as_int(main.get("humidity")),
                    condition=as_str(w.get("main")),
                    description=as_str(w.get("description")),
                    precipitation_probability=pop if pop is not None and 0 <= pop <= 1 else None,
                    wind_speed_ms=as_float(as_dict(d.get("wind")).get("speed")),
                    clouds_pct=as_int(as_dict(d.get("clouds")).get("all")),
                    rain_3h_mm=as_float(as_dict(d.get("rain")).get("3h")),
                    snow_3h_mm=as_float(as_dict(d.get("snow")).get("3h")),
                )
            )
        entries.sort(key=lambda e: e.forecast_time)
        city = as_dict(payload.get("city"))
        return WeatherForecast(
            status="ok" if entries else "empty",
            coordinate=coord,
            location_name=as_str(city.get("name")),
            timezone_offset_seconds=as_int(city.get("timezone")),
            entries=entries,
            covers_from=entries[0].forecast_time if entries else None,
            covers_to=entries[-1].forecast_time if entries else None,
            provenance=Provenance(
                provider=PROVIDER, capability=Capability.WEATHER, retrieved_at=retrieved_at
            ),
        )
