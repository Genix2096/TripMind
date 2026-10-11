from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.flights import FlightSearchRequest
from app.models.geo import PlacesSearchRequest, RouteRequest
from app.models.hotels import HotelSearchRequest
from app.models.trip import Budget, BudgetBasis, Travelers, TripState


def test_tripstate_empty_reports_all_mandatory_fields():
    fields = {m.field for m in TripState().missing_mandatory()}
    assert fields == {"origin", "destination", "departure_date", "return_date", "budget"}


def test_tripstate_complete_has_nothing_missing():
    s = TripState(
        origin="Chennai", destination="Goa", departure_date=date(2026, 12, 1), calendar_days=4,
        budget=Budget(amount=Decimal(25000), currency="inr", basis=BudgetBasis.PER_PERSON),
    )
    assert s.missing_mandatory() == []
    assert s.budget.currency == "INR"
    assert s.resolved_return_date == date(2026, 12, 4)
    assert s.nights == 3


def test_tripstate_rejects_return_before_departure():
    with pytest.raises(ValidationError):
        TripState(departure_date=date(2026, 12, 5), return_date=date(2026, 12, 1))


def test_tripstate_contradictions():
    s = TripState(
        origin="Goa", destination="goa", departure_date=date(2026, 1, 1),
        return_date=date(2026, 1, 3), calendar_days=7,
    )
    problems = " ".join(s.contradictions(today=date(2026, 6, 1)))
    assert "past" in problems and "same" in problems


def test_budget_per_person_limit():
    b = Budget(amount=Decimal(25000), currency="INR", basis=BudgetBasis.PER_PERSON)
    assert b.total_limit(3) == Decimal(75000)
    assert Budget(amount=Decimal(100), currency="USD").total_limit(3) == Decimal(100)


def test_travelers_age_bounds():
    with pytest.raises(ValidationError):
        Travelers(adults=1, children_ages=[18])
    assert Travelers(adults=2, children_ages=[3, 8]).total == 4


def test_flight_request_validation():
    ok = FlightSearchRequest(origin="maa", destination="goi", outbound_date=date(2026, 12, 1), currency="inr")
    assert (ok.origin, ok.destination, ok.currency) == ("MAA", "GOI", "INR")
    with pytest.raises(ValidationError):
        FlightSearchRequest(origin="Chennai", destination="GOI", outbound_date=date(2026, 12, 1), currency="INR")
    with pytest.raises(ValidationError):
        FlightSearchRequest(origin="MAA", destination="MAA", outbound_date=date(2026, 12, 1), currency="INR")
    with pytest.raises(ValidationError):
        FlightSearchRequest(
            origin="MAA", destination="GOI", outbound_date=date(2026, 12, 5),
            return_date=date(2026, 12, 1), currency="INR",
        )


def test_hotel_request_validation():
    base = {"query": "hotels in Goa", "check_in": date(2026, 12, 1), "check_out": date(2026, 12, 4), "currency": "INR"}
    assert HotelSearchRequest(**base).nights == 3
    with pytest.raises(ValidationError):
        HotelSearchRequest(**{**base, "check_out": date(2026, 12, 1)})
    with pytest.raises(ValidationError):
        HotelSearchRequest(**base, children_ages=[0])
    with pytest.raises(ValidationError):
        HotelSearchRequest(**base, min_rating=3.0)
    with pytest.raises(ValidationError):
        HotelSearchRequest(**base, sort_by="random_sort")
    assert HotelSearchRequest(**base, sort_by="lowest_price").sort_by == "lowest_price"


def test_geo_request_validation():
    with pytest.raises(ValidationError):
        PlacesSearchRequest(categories=["Tourism Sights!"], center={"lat": 1, "lon": 1})
    with pytest.raises(ValidationError):
        RouteRequest(waypoints=[{"lat": 1, "lon": 1}])
    with pytest.raises(ValidationError):
        RouteRequest(waypoints=[{"lat": 1, "lon": 1}, {"lat": 2, "lon": 2}], mode="teleport")
