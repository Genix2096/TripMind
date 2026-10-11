"""Decides which requested dates a retrieved forecast can honestly cover. Pure function, no I/O."""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum

from pydantic import BaseModel

from app.models.weather import ForecastEntry, WeatherForecast


class Coverage(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    BEYOND_FORECAST_HORIZON = "unavailable_beyond_horizon"
    BEFORE_FORECAST_WINDOW = "unavailable_before_window"
    NO_FORECAST_DATA = "unavailable_no_data"


class DateWeather(BaseModel):
    date: date
    coverage: Coverage
    entries: list[ForecastEntry] = []
    reason: str | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    max_precipitation_probability: float | None = None


_FULL_DAY_ENTRIES = 8  # 3-hour blocks


def assess_dates(forecast: WeatherForecast, dates: list[date]) -> list[DateWeather]:
    if not forecast.entries:
        return [
            DateWeather(date=d, coverage=Coverage.NO_FORECAST_DATA, reason="The provider returned no forecast entries.")
            for d in dates
        ]
    offset = timedelta(seconds=forecast.timezone_offset_seconds or 0)
    by_day: dict[date, list[ForecastEntry]] = {}
    for e in forecast.entries:
        by_day.setdefault((e.forecast_time + offset).date(), []).append(e)
    first, last = min(by_day), max(by_day)

    out: list[DateWeather] = []
    for d in dates:
        entries = by_day.get(d, [])
        if not entries:
            if d > last:
                out.append(
                    DateWeather(
                        date=d,
                        coverage=Coverage.BEYOND_FORECAST_HORIZON,
                        reason=f"No reliable forecast: the provider forecast only reaches {last.isoformat()}.",
                    )
                )
            elif d < first:
                out.append(
                    DateWeather(
                        date=d,
                        coverage=Coverage.BEFORE_FORECAST_WINDOW,
                        reason="This date is before the start of the retrieved forecast.",
                    )
                )
            else:
                out.append(DateWeather(date=d, coverage=Coverage.NO_FORECAST_DATA, reason="No entries for this date."))
            continue
        temps = [t for e in entries for t in (e.temp_min_c, e.temp_max_c, e.temp_c) if t is not None]
        pops = [e.precipitation_probability for e in entries if e.precipitation_probability is not None]
        partial = len(entries) < _FULL_DAY_ENTRIES
        out.append(
            DateWeather(
                date=d,
                coverage=Coverage.PARTIAL if partial else Coverage.AVAILABLE,
                entries=entries,
                reason=f"Only {len(entries)} of {_FULL_DAY_ENTRIES} 3-hour blocks are covered." if partial else None,
                temp_min_c=min(temps) if temps else None,
                temp_max_c=max(temps) if temps else None,
                max_precipitation_probability=max(pops) if pops else None,
            )
        )
    return out
