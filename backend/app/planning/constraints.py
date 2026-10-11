"""Deterministic hard-constraint validation.

A candidate is only *violating* when provider data establishes the violation. Missing data makes a
constraint *unverifiable*, never silently satisfied and never silently violated.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.flights import FlightOption
from app.models.hotels import HotelOption
from app.models.trip import HardConstraints


class Finding(BaseModel):
    constraint: str
    detail: str


class ConstraintReport(BaseModel):
    violations: list[Finding] = Field(default_factory=list)
    unverifiable: list[Finding] = Field(default_factory=list)

    @property
    def passes(self) -> bool:
        """No established violation (may still contain unverifiable constraints)."""
        return not self.violations

    @property
    def fully_verified(self) -> bool:
        return not self.violations and not self.unverifiable


def check_flight(
    option: FlightOption, constraints: HardConstraints, *, budget_currency: str | None = None
) -> ConstraintReport:
    r = ConstraintReport()

    if constraints.max_flight_stops is not None:
        if option.stops is None:
            r.unverifiable.append(Finding(constraint="max_flight_stops", detail="Stops not provided."))
        elif option.stops > constraints.max_flight_stops:
            r.violations.append(
                Finding(
                    constraint="max_flight_stops",
                    detail=f"{option.stops} stop(s) exceeds the maximum of {constraints.max_flight_stops}.",
                )
            )

    if constraints.max_flight_duration_minutes is not None:
        d = option.total_duration_minutes
        if d is None:
            r.unverifiable.append(
                Finding(constraint="max_flight_duration", detail="Total duration not provided.")
            )
        elif d > constraints.max_flight_duration_minutes:
            r.violations.append(
                Finding(
                    constraint="max_flight_duration",
                    detail=f"{d} min exceeds the maximum of {constraints.max_flight_duration_minutes} min.",
                )
            )

    if constraints.max_flight_total is not None:
        _check_price_cap(
            r, "max_flight_total", option.price.amount if option.price else None,
            option.price.currency if option.price else None, constraints.max_flight_total, budget_currency,
        )
        if option.price is not None and option.price_scope.value == "unspecified_by_provider":
            r.unverifiable.append(
                Finding(
                    constraint="max_flight_total",
                    detail="Provider does not state whether the price covers one or all travelers.",
                )
            )
    return r


def check_hotel(
    option: HotelOption, constraints: HardConstraints, *, budget_currency: str | None = None
) -> ConstraintReport:
    r = ConstraintReport()

    if constraints.min_hotel_rating is not None:
        if option.rating is None:
            r.unverifiable.append(Finding(constraint="min_hotel_rating", detail="No rating provided."))
        elif option.rating < constraints.min_hotel_rating:
            r.violations.append(
                Finding(
                    constraint="min_hotel_rating",
                    detail=f"Rating {option.rating:.1f} is below the minimum of {constraints.min_hotel_rating}.",
                )
            )

    if constraints.min_hotel_class is not None:
        if option.hotel_class is None:
            r.unverifiable.append(Finding(constraint="min_hotel_class", detail="No star class provided."))
        elif option.hotel_class < constraints.min_hotel_class:
            r.violations.append(
                Finding(
                    constraint="min_hotel_class",
                    detail=f"{option.hotel_class}-star is below the minimum of {constraints.min_hotel_class}-star.",
                )
            )

    if constraints.max_hotel_total is not None:
        total = option.total_rate.amount if option.total_rate else None
        _check_price_cap(
            r, "max_hotel_total", total.amount if total else None, total.currency if total else None,
            constraints.max_hotel_total, budget_currency,
        )

    present = {a.lower() for a in option.amenities}
    excluded = {a.lower() for a in option.excluded_amenities}
    for wanted in constraints.required_hotel_amenities:
        w = wanted.strip().lower()
        if any(w in a for a in present):
            continue
        if any(w in a and a.startswith("no ") for a in excluded):
            r.violations.append(
                Finding(constraint="required_amenity", detail=f"Provider lists '{wanted}' as unavailable.")
            )
        else:
            # Amenity lists can be incomplete, so absence is not proof.
            r.unverifiable.append(
                Finding(constraint="required_amenity", detail=f"'{wanted}' not confirmed by provider data.")
            )
    return r


def _check_price_cap(
    report: ConstraintReport,
    name: str,
    amount: Decimal | None,
    currency: str | None,
    cap: Decimal,
    cap_currency: str | None,
) -> None:
    if amount is None or currency is None:
        report.unverifiable.append(Finding(constraint=name, detail="No price provided."))
    elif cap_currency is None or currency != cap_currency:
        report.unverifiable.append(
            Finding(
                constraint=name,
                detail=f"Price is in {currency} but the cap currency is {cap_currency or 'unknown'}; not converted.",
            )
        )
    elif amount > cap:
        report.violations.append(
            Finding(constraint=name, detail=f"{amount} {currency} exceeds the cap of {cap} {currency}.")
        )
