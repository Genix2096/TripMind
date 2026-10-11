from datetime import date
from decimal import Decimal

from app.models.common import Capability, Money, Provenance
from app.models.flights import FlightOption, FlightSearchRequest, PriceScope
from app.models.hotels import HotelOption, HotelPrice, HotelSearchRequest
from app.models.trip import Budget, BudgetBasis, HardConstraints
from app.planning.budget import (
    BudgetStatus,
    CostCategory,
    CostClass,
    evaluate_budget,
    flight_cost_item,
    hotel_cost_item,
    unknown_item,
    user_assumption_item,
)
from app.planning.constraints import check_flight, check_hotel
from app.providers.serpapi.flights import SerpApiFlightsAdapter
from app.providers.serpapi.hotels import SerpApiHotelsAdapter
from tests import fixtures
from tests.conftest import NOW

PROV = Provenance(provider="p", capability=Capability.FLIGHTS, retrieved_at=NOW)


def flight(price=5000, stops=0, duration=120, scope=PriceScope.UNSPECIFIED, currency="INR"):
    return FlightOption(
        option_id="f", stops=stops, total_duration_minutes=duration, price_scope=scope,
        price=Money(amount=Decimal(price), currency=currency) if price is not None else None,
        provenance=PROV,
    )


def hotel(total=None, nightly=None, rating=4.0, klass=4, amenities=(), excluded=()):
    def hp(v):
        return HotelPrice(amount=Money(amount=Decimal(v), currency="INR")) if v is not None else None

    return HotelOption(
        hotel_id="h", name="H", total_rate=hp(total), nightly_rate=hp(nightly), rating=rating,
        hotel_class=klass, amenities=list(amenities), excluded_amenities=list(excluded), provenance=PROV,
    )


BUDGET = Budget(amount=Decimal(20000), currency="INR", basis=BudgetBasis.TOTAL)


# ---------------- budget ------------------------------------------------------------------


def test_unknown_costs_are_never_zero_and_status_is_incomplete():
    items = [flight_cost_item(flight(5000), 1), hotel_cost_item(hotel(total=8000), 3)]
    r = evaluate_budget(BUDGET, 1, items)
    assert r.status == BudgetStatus.INCOMPLETE
    assert r.known_subtotal.amount == Decimal(13000)
    assert set(r.missing_categories) == {CostCategory.LOCAL_TRANSPORT, CostCategory.FOOD, CostCategory.ATTRACTIONS}
    assert r.remaining_after_known_costs.amount == Decimal(7000) and not r.remaining_is_final


def test_within_budget_only_when_everything_is_known():
    items = [flight_cost_item(flight(5000), 1), hotel_cost_item(hotel(total=8000), 3)]
    for cat in (CostCategory.LOCAL_TRANSPORT, CostCategory.FOOD, CostCategory.ATTRACTIONS):
        items.append(user_assumption_item(cat, cat.value, Decimal(1000), "INR", "my own figure"))
    r = evaluate_budget(BUDGET, 1, items)
    assert r.status == BudgetStatus.WITHIN_BUDGET and r.remaining_is_final
    assert r.known_subtotal.amount == Decimal(16000) and r.missing_categories == []


def test_exceeded_even_with_missing_costs():
    items = [flight_cost_item(flight(15000), 1), hotel_cost_item(hotel(total=9000), 3)]
    r = evaluate_budget(BUDGET, 1, items)
    assert r.status == BudgetStatus.EXCEEDED and r.known_subtotal.amount == Decimal(24000)


def test_hotel_total_preferred_and_nightly_calculation_labelled():
    assert hotel_cost_item(hotel(total=9000, nightly=1000), 3).amount == Decimal(9000)
    calc = hotel_cost_item(hotel(nightly=2500), 3)
    assert calc.amount == Decimal(7500) and calc.cost_class == CostClass.CALCULATED
    none = hotel_cost_item(hotel(), 3)
    assert none.amount is None and none.cost_class == CostClass.UNKNOWN


def test_flight_price_scope_for_groups_requires_explicit_assumption():
    unknown = flight_cost_item(flight(5000), 3)
    assert unknown.cost_class == CostClass.UNKNOWN and unknown.amount is None
    per = flight_cost_item(flight(5000), 3, assumed_scope=PriceScope.PER_TRAVELER)
    assert per.amount == Decimal(15000) and per.cost_class == CostClass.USER_ASSUMPTION
    total = flight_cost_item(flight(5000), 3, assumed_scope=PriceScope.TOTAL_ALL_TRAVELERS)
    assert total.amount == Decimal(5000) and total.cost_class == CostClass.USER_ASSUMPTION
    single = flight_cost_item(flight(5000), 1)
    assert single.cost_class == CostClass.VERIFIED_PROVIDER


def test_missing_flight_price_is_unknown():
    item = flight_cost_item(flight(price=None), 1)
    assert item.cost_class == CostClass.UNKNOWN and item.amount is None
    assert flight_cost_item(None, 1).cost_class == CostClass.UNKNOWN


def test_currency_mismatch_not_converted():
    items = [flight_cost_item(flight(100, currency="USD"), 1), hotel_cost_item(hotel(total=8000), 3)]
    r = evaluate_budget(BUDGET, 1, items)
    assert r.known_subtotal.amount == Decimal(8000) and len(r.currency_mismatches) == 1
    assert CostCategory.FLIGHTS in r.missing_categories
    assert r.status == BudgetStatus.INCOMPLETE


def test_per_person_budget_scales_with_travelers():
    b = Budget(amount=Decimal(10000), currency="INR", basis=BudgetBasis.PER_PERSON)
    r = evaluate_budget(b, 4, [unknown_item(CostCategory.FLIGHTS, "Flights", "n/a")])
    assert r.budget_limit.amount == Decimal(40000)


def test_no_budget_status():
    r = evaluate_budget(None, 1, [hotel_cost_item(hotel(total=1000), 1)])
    assert r.status == BudgetStatus.NO_BUDGET and r.remaining_after_known_costs is None


# ---------------- constraints -------------------------------------------------------------


def test_flight_constraints_violation_vs_unverifiable():
    c = HardConstraints(max_flight_stops=0, max_flight_duration_minutes=180)
    assert check_flight(flight(stops=0, duration=120), c).fully_verified
    bad = check_flight(flight(stops=1, duration=240), c)
    assert not bad.passes and {v.constraint for v in bad.violations} == {"max_flight_stops", "max_flight_duration"}
    unknown = check_flight(flight(stops=0, duration=None), c)
    assert unknown.passes and not unknown.fully_verified


def test_price_caps_respect_currency_and_scope():
    c = HardConstraints(max_flight_total=Decimal(4000))
    over = check_flight(flight(5000), c, budget_currency="INR")
    assert [v.constraint for v in over.violations] == ["max_flight_total"]
    assert any("one or all travelers" in u.detail for u in over.unverifiable)
    wrong_cur = check_flight(flight(5000, currency="USD"), c, budget_currency="INR")
    assert wrong_cur.passes and wrong_cur.unverifiable


def test_hotel_constraints():
    c = HardConstraints(min_hotel_rating=4.0, min_hotel_class=4, required_hotel_amenities=["pool", "gym"],
                        max_hotel_total=Decimal(10000))
    ok = check_hotel(hotel(total=9000, amenities=["Pool", "Gym"]), c, budget_currency="INR")
    assert ok.fully_verified
    low = check_hotel(hotel(total=12000, rating=3.5, klass=3, amenities=["Pool", "Gym"]), c, budget_currency="INR")
    assert {v.constraint for v in low.violations} == {"min_hotel_rating", "min_hotel_class", "max_hotel_total"}
    # missing amenity data is unverifiable, not a violation
    unk = check_hotel(hotel(total=9000, amenities=["Pool"]), c, budget_currency="INR")
    assert unk.passes and len(unk.unverifiable) == 1
    # explicit provider "No gym" is an established violation
    viol = check_hotel(hotel(total=9000, amenities=["Pool"], excluded=["No gym"]), c, budget_currency="INR")
    assert not viol.passes
    no_rating = check_hotel(hotel(total=9000, rating=None, amenities=["Pool", "Gym"]), c, budget_currency="INR")
    assert no_rating.passes and not no_rating.fully_verified


def test_end_to_end_parsed_data_feeds_budget_without_invention():
    req = HotelSearchRequest(query="hotels in X", check_in=date(2026, 12, 1), check_out=date(2026, 12, 5), currency="INR")
    hotels = SerpApiHotelsAdapter.parse_response(fixtures.HOTELS_OK, req, {}, retrieved_at=NOW).items
    freq = FlightSearchRequest(origin="AAA", destination="BBB", outbound_date=date(2026, 12, 1), currency="INR")
    flights = SerpApiFlightsAdapter.parse_response(fixtures.FLIGHTS_OK, freq, {}, retrieved_at=NOW).items
    assert hotel_cost_item(hotels[1], 4).cost_class == CostClass.UNKNOWN  # display-only price
    assert flight_cost_item(flights[1], 1).cost_class == CostClass.UNKNOWN  # price missing
    ok = evaluate_budget(BUDGET, 1, [flight_cost_item(flights[0], 1), hotel_cost_item(hotels[0], 4)])
    assert ok.known_subtotal.amount == Decimal(21400) and ok.status == BudgetStatus.EXCEEDED


def test_synthesis_input_size_reduction_preserves_constraints():
    import json
    from app.api.routes.planning import (
        summarize_flight_item,
        summarize_hotel_item,
        summarize_place_item,
    )
    from app.providers.serpapi.maps import SerpApiMapsAdapter

    # 1. Parse sample items using actual adapter parsers
    freq = FlightSearchRequest(origin="AAA", destination="BBB", outbound_date=date(2026, 12, 1), currency="INR")
    f_items = SerpApiFlightsAdapter.parse_response(fixtures.FLIGHTS_OK, freq, {}, retrieved_at=NOW).items
    hreq = HotelSearchRequest(query="hotels in X", check_in=date(2026, 12, 1), check_out=date(2026, 12, 5), currency="INR")
    h_items = SerpApiHotelsAdapter.parse_response(fixtures.HOTELS_OK, hreq, {}, retrieved_at=NOW).items
    m_items = SerpApiMapsAdapter.parse_response(fixtures.GOOGLE_MAPS_OK, {}, retrieved_at=NOW).items

    # 2. Verify flight summary preserves constraints
    f_summary = [summarize_flight_item(f) for f in f_items[:3]]
    assert len(f_summary) >= 1
    top_flight = f_summary[0]
    assert top_flight["airline"] == "TestAir"
    assert "TA 1" in top_flight["flight_numbers"]
    assert "AAA" in top_flight["departure"]
    assert "BBB" in top_flight["arrival"]
    assert top_flight["price"] == "INR 5400"
    assert top_flight["stops"] == 0

    # 3. Verify hotel summary preserves constraints
    h_summary = [summarize_hotel_item(h) for h in h_items[:3]]
    assert len(h_summary) >= 1
    top_hotel = h_summary[0]
    assert top_hotel["name"] == "Test Resort"
    assert top_hotel["stars"] == 4
    assert top_hotel["rating"] == 4.3
    assert top_hotel["nightly_rate"] == "INR 4000"
    assert top_hotel["total_rate"] == "INR 16000"
    assert len(top_hotel["amenities"]) <= 5

    # 4. Verify place summary preserves constraints
    p_summary = [summarize_place_item(p) for p in m_items[:5]]
    assert len(p_summary) >= 1
    top_place = p_summary[0]
    assert top_place["name"] == "Eiffel Tower"
    assert top_place["rating"] == 4.7
    assert "Monument" in top_place["categories"]
    assert "Champ de Mars" in top_place["address"]
    assert "11:45 PM" in top_place["opening_hours"]

    # 5. Verify total serialized footprint is lean (well under 2,000 characters, < 500 tokens)
    serialized = json.dumps({"flights": f_summary, "hotels": h_summary, "places": p_summary})
    assert len(serialized) < 2000

    # 6. Verify token estimate leaves ample margin below 7,500 TPM threshold
    estimated_tokens = int(len(serialized) / 4.0)
    assert estimated_tokens < 500
    # Combined with 1500 max_tokens requested output, total usage is ~2000 tokens << 7500 limit
    assert estimated_tokens + 1500 < 3500

