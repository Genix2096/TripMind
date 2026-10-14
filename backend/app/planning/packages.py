"""Deterministic Travel Package generation, budgeting and option re-selection.

Everything here is pure Python: no LLM, no provider calls. Packages are built only from options the
existing (already authorised) searches returned; nothing is invented.

Flight price semantics (single rule used for ranking, package generation and the official report)
-----------------------------------------------------------------------------------------------
* ``PlanningCoordinator`` searches each leg as its own ONE-WAY search (outbound, then the reversed return
  leg), so a returned price normally belongs to one leg and the two legs are summed.
* SerpApi does not say whether a price covers one traveler or all of them (``price_scope`` stays
  UNSPECIFIED). For a single traveler the price is used as quoted. For more than one traveler the cost is
  UNKNOWN unless the provider stated a scope, so the package is classified ``incomplete`` instead of
  guessing. No scope is assumed anywhere in this module.
* If an option is itself a round-trip fare (``trip_type`` says round trip, or the return leg is still
  pending), that fare covers both legs and is counted once; the other leg is recorded as included.

Package budgets cover flights + accommodation only. Food, local transport and attractions have no
provider-priced data, so they are listed as excluded/unknown and never treated as zero.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from app.models.common import Money
from app.models.day_plan import Activity, DayPlan
from app.models.flights import FlightOption
from app.models.hotels import HotelOption
from app.models.packages import BudgetClassification, TravelPackage
from app.models.trip import TripState
from app.planning.budget import (
    BudgetReport,
    BudgetStatus,
    CostCategory,
    CostClass,
    CostItem,
    evaluate_budget,
    flight_cost_item,
    hotel_cost_item,
    unknown_item,
)
from app.planning.constraints import check_flight, check_hotel

logger = logging.getLogger("app.planning.packages")

PACKAGE_EXPECTED = (CostCategory.FLIGHTS, CostCategory.ACCOMMODATION)
_EXCLUDED_CATEGORIES = (
    (CostCategory.LOCAL_TRANSPORT, "Local transport"),
    (CostCategory.FOOD, "Food"),
    (CostCategory.ATTRACTIONS, "Attractions & activities"),
)
_BIG = Decimal("1E+12")


class SelectionError(ValueError):
    """The requested option is not one of the options that belong to the package."""


# ---------------------------------------------------------------------------
# 1. Flight and hotel normalization, direction classification, deduplication
# ---------------------------------------------------------------------------


def _dep_date(f: FlightOption) -> date | None:
    if not f.segments:
        return None
    t = f.segments[0].departure.local_time
    return t.date() if t else None


def _flight_signature(f: FlightOption) -> str:
    """Identity of a flight itinerary independent of its listed price (same itinerary = same flight)."""
    parts: list[str] = []
    identifying = False
    for s in f.segments:
        fn = (s.flight_number or "").replace(" ", "").upper()
        dep_t = s.departure.local_time.strftime("%Y-%m-%dT%H:%M") if s.departure.local_time else ""
        arr_t = s.arrival.local_time.strftime("%Y-%m-%dT%H:%M") if s.arrival.local_time else ""
        if fn or dep_t:
            identifying = True
        parts.append(
            f"{(s.airline or '').strip().lower()}_{fn}_{(s.departure.code or '').strip().upper()}"
            f"_{(s.arrival.code or '').strip().upper()}_{dep_t}_{arr_t}"
        )
    sig = "|".join(parts)
    if not identifying:
        # Nothing identifies the itinerary, so do not collapse genuinely different unlabeled options.
        price = f"{f.price.amount}_{f.price.currency}" if f.price else "noprice"
        sig += f"#{f.total_duration_minutes}#{price}"
    return sig


def _classify_direction(f: FlightOption, ts: TripState) -> str | None:
    """Outbound/return from the searched leg, never from comparing city names to IATA codes."""
    if f.direction in ("outbound", "return"):
        return f.direction
    oid = f.option_id.lower()
    if oid.startswith("return"):
        return "return"
    if oid.startswith("outbound"):
        return "outbound"
    d = _dep_date(f)
    if d is not None:
        if ts.return_date and d == ts.return_date and d != ts.departure_date:
            return "return"
        if ts.departure_date and d == ts.departure_date and d != ts.return_date:
            return "outbound"
    return None


def _strip_raw(option: Any) -> None:
    option.provenance = option.provenance.model_copy(update={"raw": None})


def normalize_flights(
    flights: list[FlightOption], ts: TripState
) -> tuple[list[FlightOption], list[FlightOption], list[str]]:
    """Classify, validate dates, dedupe and assign stable IDs. Returns (outbounds, returns, notes)."""
    notes: list[str] = []
    buckets: dict[str, dict[str, FlightOption]] = {"outbound": {}, "return": {}}
    order: dict[str, list[str]] = {"outbound": [], "return": []}
    unclassified = date_mismatch = unexpected_return = no_segments = 0

    for f in flights:
        if not f.segments:
            no_segments += 1
            continue
        direction = _classify_direction(f, ts)
        if direction is None:
            unclassified += 1
            continue
        if direction == "return" and not ts.return_date:
            unexpected_return += 1
            continue
        expected = ts.departure_date if direction == "outbound" else ts.return_date
        d = _dep_date(f)
        if expected and d and d != expected:
            date_mismatch += 1
            continue
        sig = _flight_signature(f)
        existing = buckets[direction].get(sig)
        if existing is None:
            buckets[direction][sig] = f
            order[direction].append(sig)
        elif f.price and (existing.price is None or f.price.amount < existing.price.amount):
            buckets[direction][sig] = f  # same itinerary listed twice: keep the lowest quote

    if no_segments:
        notes.append(f"{no_segments} flight result(s) without segment details were ignored.")
    if unclassified:
        notes.append(f"{unclassified} flight result(s) could not be tied to an outbound or return search and were ignored.")
    if unexpected_return:
        notes.append(f"{unexpected_return} return-leg flight result(s) were ignored because no return date was requested.")
    if date_mismatch:
        notes.append(f"{date_mismatch} flight result(s) were ignored because their departure date does not match the requested date.")

    result: dict[str, list[FlightOption]] = {"outbound": [], "return": []}
    for direction in ("outbound", "return"):
        for i, sig in enumerate(order[direction]):
            copied = buckets[direction][sig].model_copy(deep=True)
            copied.option_id = f"{direction}-flight-{i}"
            copied.direction = direction  # type: ignore[assignment]
            _strip_raw(copied)
            result[direction].append(copied)
    return result["outbound"], result["return"], notes


def normalize_hotels(hotels: list[HotelOption]) -> list[HotelOption]:
    """Dedupe distinct properties (first listing wins) and assign stable IDs."""
    deduped: list[HotelOption] = []
    seen: set[str] = set()
    for h in hotels:
        token = (h.property_token or "").strip()
        if token:
            key = f"t:{token}"
        else:
            coords = f"{h.coordinates.lat:.3f},{h.coordinates.lon:.3f}" if h.coordinates else ""
            key = f"n:{(h.name or '').strip().lower()}|{coords}"
        if key in seen and key not in ("n:|",):
            continue
        seen.add(key)
        copied = h.model_copy(deep=True)
        copied.hotel_id = f"hotel-{len(deduped)}"
        _strip_raw(copied)
        deduped.append(copied)
    return deduped


def collect_hotel_names(hotels: list[HotelOption]) -> set[str]:
    return {h.name.strip().lower() for h in hotels if h.name and len(h.name.strip()) >= 3}


# ---------------------------------------------------------------------------
# 2. Package budget (the one calculation used everywhere)
# ---------------------------------------------------------------------------


@dataclass
class PackageBudget:
    report: BudgetReport
    classification: BudgetClassification
    total_cost: Money | None
    known_subtotal: Money | None
    remaining: Money | None
    over: Money | None
    warnings: list[str] = field(default_factory=list)
    complete: bool = False


def _is_round_trip_fare(o: FlightOption | None) -> bool:
    if o is None:
        return False
    return bool(o.return_leg_details_pending or "round" in (o.trip_type or "").lower())


def _included_item(label: str, ref: FlightOption, why: str) -> CostItem:
    assert ref.price is not None
    return CostItem(
        category=CostCategory.FLIGHTS, label=label, amount=Decimal(0), currency=ref.price.currency,
        cost_class=CostClass.CALCULATED, basis=why, source=ref.provenance,
    )


def calculate_package_budget(
    ts: TripState,
    out: FlightOption | None,
    ret: FlightOption | None,
    hotel: HotelOption | None,
) -> PackageBudget:
    travelers = ts.travelers.total
    nights = ts.nights or 0
    needs_return = ts.return_date is not None
    items: list[CostItem] = []
    warnings: list[str] = []

    covering = None  # which listing carries a round-trip fare
    if needs_return and out is not None and ret is not None:
        if _is_round_trip_fare(out) and out.price:
            covering = "out"
        elif _is_round_trip_fare(ret) and ret.price:
            covering = "ret"

    # Outbound
    if out is None:
        items.append(unknown_item(CostCategory.FLIGHTS, "Outbound flight", "No outbound flight selected."))
    elif covering == "ret":
        items.append(_included_item("Outbound flight", ret, "Included in the round-trip fare quoted on the return listing; not added again."))  # type: ignore[arg-type]
    else:
        it = flight_cost_item(out, travelers)
        it.label = "Round-trip fare (quoted on outbound listing)" if covering == "out" else "Outbound flight"
        items.append(it)

    # Return
    if needs_return:
        if ret is None:
            items.append(unknown_item(CostCategory.FLIGHTS, "Return flight", "No return flight selected."))
        elif covering == "out":
            items.append(_included_item("Return flight", out, "Included in the round-trip fare quoted on the outbound listing; not added again."))  # type: ignore[arg-type]
        else:
            it = flight_cost_item(ret, travelers)
            it.label = "Round-trip fare (quoted on return listing)" if covering == "ret" else "Return flight"
            items.append(it)

    # Hotel
    if hotel is None:
        items.append(unknown_item(CostCategory.ACCOMMODATION, "Accommodation", "No hotel selected."))
    else:
        items.append(hotel_cost_item(hotel, nights))

    for it in items:
        if it.cost_class == CostClass.UNKNOWN:
            warnings.append(f"{it.label}: cost unknown. {it.basis}")

    for cat, label in _EXCLUDED_CATEGORIES:
        items.append(unknown_item(cat, label, "Excluded from package total: no provider-priced data for this category."))

    report = evaluate_budget(ts.budget, travelers, items, expected=PACKAGE_EXPECTED)

    core = [i for i in items if i.category in PACKAGE_EXPECTED]
    complete = all(i.amount is not None and i.cost_class != CostClass.UNKNOWN for i in core) and not report.currency_mismatches
    if report.currency_mismatches:
        warnings.append("Some prices are in a different currency than the budget and were not converted or summed.")

    limit = report.budget_limit
    total: Money | None = None
    remaining: Money | None = None
    over: Money | None = None
    if not complete:
        classification = BudgetClassification.INCOMPLETE
        warnings.append("Total is incomplete and must not be read as the final trip cost.")
        if report.status == BudgetStatus.EXCEEDED:
            warnings.append("Known costs alone already exceed the budget (lower bound); the total is not labelled over budget because it is incomplete.")
    else:
        total = report.known_subtotal
        assert total is not None
        if limit is None:
            classification = BudgetClassification.NO_BUDGET
        elif total.amount <= limit.amount:
            classification = BudgetClassification.WITHIN_BUDGET
            remaining = Money(amount=limit.amount - total.amount, currency=limit.currency)
        else:
            classification = BudgetClassification.OVER_BUDGET
            over = Money(amount=total.amount - limit.amount, currency=limit.currency)

    warnings.append("Totals cover flights and accommodation only; food, local transport and activities are excluded.")
    warnings.append("Prices are provider search quotes; taxes, fees, baggage and cancellation terms are not confirmed.")
    if ts.rooms and ts.rooms > 1:
        warnings.append(f"Hotel prices are for the provider's search occupancy; {ts.rooms} rooms were not applied.")

    return PackageBudget(
        report=report, classification=classification, total_cost=total, known_subtotal=report.known_subtotal,
        remaining=remaining, over=over, warnings=warnings, complete=complete,
    )


# ---------------------------------------------------------------------------
# 3. Itinerary synchronisation
# ---------------------------------------------------------------------------

_LOGISTICS_MARKERS = ("flight", "check-in", "check in", "check-out", "check out", "overnight", "airport transfer")


def _is_logistics(a: Activity, hotel_names: set[str]) -> bool:
    n = a.name.lower()
    return any(m in n for m in _LOGISTICS_MARKERS) or any(h in n for h in hotel_names)


def _day_index(days: list[DayPlan], d: date | None, default: int) -> int | None:
    if d is None or not any(day.date for day in days):
        return default
    for i, day in enumerate(days):
        if day.date == d:
            return i
    return None


def _hhmm(dt: datetime | None) -> str | None:
    return dt.strftime("%H:%M") if dt else None


def adapt_itinerary_for_package(
    base_day_wise: list[DayPlan],
    out: FlightOption | None,
    ret: FlightOption | None,
    hotel: HotelOption | None,
    destination: str,
    hotel_names: set[str] | None = None,
    stay_start: date | None = None,
    stay_end: date | None = None,
) -> tuple[list[DayPlan], list[str]]:
    """Rebuild the package itinerary from the stored base plan for the CURRENT selections.

    Always starts from the base plan so previously selected flights/hotels never linger. Only real
    provider times are used; no durations, opening hours or transfer times are invented. Timing problems
    are flagged in ``scheduling_conflicts`` rather than silently rescheduled.
    """
    days = copy.deepcopy(base_day_wise)
    warnings: list[str] = []
    if not days:
        return days, warnings

    names = set(hotel_names or set())
    if hotel and hotel.name and len(hotel.name.strip()) >= 3:
        names.add(hotel.name.strip().lower())
    for day in days:
        day.activities = [a for a in day.activities if not _is_logistics(a, names)]

    pre: dict[int, list[Activity]] = {i: [] for i in range(len(days))}
    post: dict[int, list[Activity]] = {i: [] for i in range(len(days))}
    arrival_idx: int | None = None
    depart_idx: int | None = None

    if out and out.segments:
        first, last = out.segments[0], out.segments[-1]
        arr_dt, dep_dt = last.arrival.local_time, first.departure.local_time
        arrival_idx = _day_index(days, arr_dt.date() if arr_dt else None, 0)
        if arr_dt is None:
            days[0].missing_information.append("Outbound arrival time was not provided; arrival-day timing is not validated.")
        if arrival_idx is None:
            warnings.append(f"Outbound flight arrives on {arr_dt.date() if arr_dt else '?'}, outside the itinerary dates.")
            arrival_idx = 0
        else:
            for i in range(arrival_idx):
                days[i].scheduling_conflicts.append(
                    f"Outbound flight arrives on {days[arrival_idx].date}; activities before arrival are not feasible."
                )
        if arr_dt and arr_dt.hour >= 18:
            days[arrival_idx].scheduling_conflicts.append(
                f"Late arrival ({_hhmm(arr_dt)}); other activities on this day may not be feasible."
            )
        if stay_start and arr_dt and arr_dt.date() > stay_start:
            warnings.append(f"Hotel stay starts {stay_start} but the outbound flight arrives {arr_dt.date()}; the first night may be unused.")
        label = f"{first.airline or 'Flight'} {first.flight_number or ''}".strip()
        dep_s, arr_s = _hhmm(dep_dt), _hhmm(arr_dt)
        pre[arrival_idx].append(Activity(
            name=f"Outbound flight to {destination}: {label}",
            location=f"{first.departure.code or '?'} → {last.arrival.code or '?'}",
            description=(
                f"Departs {dep_dt:%Y-%m-%d %H:%M}" if dep_dt else "Departure time not provided"
            ) + (f", arrives {arr_dt:%Y-%m-%d %H:%M}." if arr_dt else ", arrival time not provided."),
            time_window=f"{dep_s} – {arr_s}" if dep_s and arr_s else None,
            data_source="Google Flights (SerpApi)",
        ))
        if hotel:
            cin = hotel.check_in_time
            pre[arrival_idx].append(Activity(
                name=f"Hotel check-in: {hotel.name}",
                location=hotel.address or hotel.name,
                description=f"Provider check-in time: {cin}." if cin else "Check-in time was not provided by the hotel data.",
                time_window=f"From {cin}" if cin else None,
                data_source="Google Hotels (SerpApi)",
            ))

    if ret and ret.segments:
        r_first, r_last = ret.segments[0], ret.segments[-1]
        rdep, rarr = r_first.departure.local_time, r_last.arrival.local_time
        depart_idx = _day_index(days, rdep.date() if rdep else None, len(days) - 1)
        if rdep is None:
            days[-1].missing_information.append("Return departure time was not provided; departure-day timing is not validated.")
        if depart_idx is None:
            warnings.append(f"Return flight departs on {rdep.date() if rdep else '?'}, outside the itinerary dates.")
            depart_idx = len(days) - 1
        else:
            for i in range(depart_idx + 1, len(days)):
                days[i].scheduling_conflicts.append(
                    f"Return flight departs on {days[depart_idx].date}; activities after departure are not feasible."
                )
        if rdep and rdep.hour < 12:
            days[depart_idx].scheduling_conflicts.append(
                f"Early return departure ({_hhmm(rdep)}); other activities on this day may not be feasible."
            )
        if stay_end and rdep and rdep.date() != stay_end:
            warnings.append(f"Hotel stay ends {stay_end} but the return flight departs {rdep.date()}; hotel nights and flight dates do not line up.")
        if hotel:
            cout = hotel.check_out_time
            pre[depart_idx].append(Activity(
                name=f"Hotel check-out: {hotel.name}",
                location=hotel.address or hotel.name,
                description=f"Provider check-out time: {cout}." if cout else "Check-out time was not provided by the hotel data.",
                time_window=f"By {cout}" if cout else None,
                data_source="Google Hotels (SerpApi)",
            ))
        label = f"{r_first.airline or 'Flight'} {r_first.flight_number or ''}".strip()
        dep_s, arr_s = _hhmm(rdep), _hhmm(rarr)
        post[depart_idx].append(Activity(
            name=f"Return flight: {label}",
            location=f"{r_first.departure.code or '?'} → {r_last.arrival.code or '?'}",
            description=(
                f"Departs {rdep:%Y-%m-%d %H:%M}" if rdep else "Departure time not provided"
            ) + (f", arrives {rarr:%Y-%m-%d %H:%M}." if rarr else ", arrival time not provided."),
            time_window=f"{dep_s} – {arr_s}" if dep_s and arr_s else None,
            data_source="Google Flights (SerpApi)",
        ))

    if hotel and arrival_idx is not None and depart_idx is not None:
        for i in range(arrival_idx + 1, depart_idx):
            if days[i].activities:
                post[i].append(Activity(
                    name=f"Overnight stay: {hotel.name}",
                    location=hotel.address or hotel.name,
                    data_source="Google Hotels (SerpApi)",
                ))

    for i, day in enumerate(days):
        day.activities = [*pre[i], *day.activities, *post[i]]
    return days, warnings


# ---------------------------------------------------------------------------
# 4. Package composition
# ---------------------------------------------------------------------------


def _score_hotel(h: HotelOption) -> float:
    return (h.rating or 3.5) * 2.0 + (h.hotel_class or 3) * 1.5 + min((h.review_count or 0) / 500.0, 1.0)


def _score_flight(f: FlightOption) -> float:
    score = 10.0 + (3.0 if f.provider_ranked_best else 0.0)
    score -= (f.stops or 0) * 2.5
    score -= (f.total_duration_minutes or 300) / 120.0
    return score


def _flight_price(f: FlightOption) -> Decimal:
    return f.price.amount if f.price else _BIG


def _rank_flights(flights: list[FlightOption]) -> list[FlightOption]:
    return sorted(flights, key=lambda f: (-_score_flight(f), _flight_price(f), f.option_id))


def _rank_hotels(hotels: list[HotelOption], nights: int) -> list[HotelOption]:
    return sorted(hotels, key=lambda h: (-_score_hotel(h), hotel_cost_item(h, nights).amount or _BIG, h.hotel_id))


def _shortlist(items: list[Any], score: Callable[[Any], float], price: Callable[[Any], Decimal], ident: Callable[[Any], str]) -> list[Any]:
    by_score = sorted(items, key=lambda o: (-score(o), price(o), ident(o)))
    by_price = sorted(items, key=lambda o: (price(o), -score(o), ident(o)))
    out: list[Any] = []
    seen: set[str] = set()
    for o in by_score[:5] + by_price[:3]:
        if ident(o) not in seen:
            seen.add(ident(o))
            out.append(o)
    return out


@dataclass
class Candidate:
    out: FlightOption
    ret: FlightOption | None
    hotel: HotelOption
    pb: PackageBudget
    score: float

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.out.option_id, self.ret.option_id if self.ret else "", self.hotel.hotel_id)

    @property
    def sort_cost(self) -> Decimal:
        m = self.pb.total_cost or self.pb.known_subtotal
        return m.amount if m else _BIG


def _key_value(c: Candidate, chosen: list[Candidate]):
    return (-c.score, c.sort_cost, c.triple)


def _key_quality(c: Candidate, chosen: list[Candidate]):
    used = {x.hotel.hotel_id for x in chosen}
    return (c.hotel.hotel_id in used, -_score_hotel(c.hotel), -c.score, c.triple)


def _key_economy(c: Candidate, chosen: list[Candidate]):
    used = {x.hotel.hotel_id for x in chosen}
    return (c.hotel.hotel_id in used, c.sort_cost, c.triple)


def _pick(pool: list[Candidate], chosen: list[Candidate], key) -> Candidate | None:
    taken = {c.triple for c in chosen}
    avail = [c for c in pool if c.triple not in taken]
    return min(avail, key=lambda c: key(c, chosen)) if avail else None


def _prov(o: FlightOption | HotelOption) -> dict[str, Any]:
    p = o.provenance
    return {"provider": p.provider, "search_id": p.search_id, "retrieved_at": p.retrieved_at.isoformat(), "source_url": p.source_url}


def _compose(
    *, pkg_id: str, name: str, desc: str, tier: str, ts: TripState, base_day_wise: list[DayPlan], base_summary: str,
    out: FlightOption | None, ret: FlightOption | None, hotel: HotelOption | None,
    out_alts: list[FlightOption], ret_alts: list[FlightOption], h_alts: list[HotelOption], hotel_names: set[str],
) -> TravelPackage:
    pb = calculate_package_budget(ts, out, ret, hotel)
    destination = ts.destination or "destination"
    days, itin_warnings = adapt_itinerary_for_package(
        base_day_wise, out, ret, hotel, destination, hotel_names, ts.departure_date, ts.return_date
    )
    missing: list[str] = []
    if out is None:
        missing.append("outbound_flight")
    if ts.return_date and ret is None:
        missing.append("return_flight")
    if hotel is None:
        missing.append("hotel")
    missing += [f"price:{i.label}" for i in pb.report.items if i.category in PACKAGE_EXPECTED and i.cost_class == CostClass.UNKNOWN and i.basis.startswith(("The provider", "Provider"))]
    currency = (
        ts.budget.currency if ts.budget
        else (pb.known_subtotal.currency if pb.known_subtotal else "")
    )
    prov: dict[str, Any] = {}
    if out:
        prov["outbound_flight"] = _prov(out)
    if ret:
        prov["return_flight"] = _prov(ret)
    if hotel:
        prov["hotel"] = _prov(hotel)
    return TravelPackage(
        package_id=pkg_id, name=name, description=desc, target_tier=tier,
        budget_classification=pb.classification,
        selected_outbound_flight=out, selected_return_flight=ret, selected_hotel=hotel,
        outbound_flight_alternatives=out_alts, return_flight_alternatives=ret_alts, hotel_alternatives=h_alts,
        day_wise=days, trip_summary=f"{name}: {desc} {base_summary}".strip(),
        budget_report=pb.report, total_cost=pb.total_cost, known_subtotal=pb.known_subtotal,
        remaining_budget=pb.remaining, amount_over_budget=pb.over, currency=currency,
        is_complete=pb.complete and not missing, completeness_status="complete" if pb.complete and not missing else "incomplete",
        warnings=[*itin_warnings, *pb.warnings], missing_items=missing, provenance_summary=prov,
    )


def reselect_package(
    pkg: TravelPackage,
    ts: TripState,
    base_day_wise: list[DayPlan],
    hotel_names: set[str],
    *,
    outbound_id: str | None = None,
    return_id: str | None = None,
    hotel_id: str | None = None,
) -> TravelPackage:
    """Apply a selection by ID, restricted to this package's own options, then recompute everything."""

    def pool(sel, alts):
        return ([sel] if sel is not None else []) + list(alts)

    out_pool = pool(pkg.selected_outbound_flight, pkg.outbound_flight_alternatives)
    ret_pool = pool(pkg.selected_return_flight, pkg.return_flight_alternatives)
    h_pool = pool(pkg.selected_hotel, pkg.hotel_alternatives)

    def choose(options, wanted, attr, current, label):
        if wanted is None:
            return current
        for o in options:
            if getattr(o, attr) == wanted:
                return o
        raise SelectionError(f"{label} '{wanted}' is not an available option for {pkg.package_id}.")

    if return_id is not None and not ts.return_date:
        raise SelectionError("This trip has no return leg.")
    out = choose(out_pool, outbound_id, "option_id", pkg.selected_outbound_flight, "Outbound flight")
    ret = choose(ret_pool, return_id, "option_id", pkg.selected_return_flight, "Return flight")
    hotel = choose(h_pool, hotel_id, "hotel_id", pkg.selected_hotel, "Hotel")

    return _compose(
        pkg_id=pkg.package_id, name=pkg.name, desc=pkg.description, tier=pkg.target_tier, ts=ts,
        base_day_wise=base_day_wise, base_summary="",
        out=out, ret=ret, hotel=hotel,
        out_alts=[o for o in out_pool if out is None or o.option_id != out.option_id],
        ret_alts=[o for o in ret_pool if ret is None or o.option_id != ret.option_id],
        h_alts=[o for o in h_pool if hotel is None or o.hotel_id != hotel.hotel_id],
        hotel_names=hotel_names,
    ).model_copy(update={"trip_summary": pkg.trip_summary})


def build_travel_packages(
    trip_state: TripState,
    raw_flights: list[FlightOption],
    raw_hotels: list[HotelOption],
    base_day_wise: list[DayPlan],
    base_trip_summary: str,
    provider_statuses: dict[str, Any],
    data_notes: list[str] | None = None,
    hotel_names: set[str] | None = None,
) -> tuple[list[TravelPackage], list[str]]:
    """Build up to four distinct packages from already-fetched provider results.

    Within-budget packages come first, then at most one over-budget package. Every classification comes
    from ``calculate_package_budget``; anything the data cannot support is reported in the notes.
    """
    ts = trip_state
    notes: list[str] = list(data_notes or [])
    names = hotel_names if hotel_names is not None else collect_hotel_names(raw_hotels)
    nights = ts.nights or 0
    needs_return = ts.return_date is not None

    for cap in ("flights", "hotels"):
        st = provider_statuses.get(cap)
        if st is not None and getattr(st.status, "value", st.status) in ("error", "unavailable"):
            notes.append(f"{cap.capitalize()} search {getattr(st.status, 'value', st.status)}: {st.error_detail or 'no detail'}.")

    outbounds, returns, flight_notes = normalize_flights(raw_flights, ts)
    notes += flight_notes
    hotels = normalize_hotels(raw_hotels)

    cur = ts.budget.currency if ts.budget else None
    hc = ts.hard_constraints
    v_out = [o for o in outbounds if check_flight(o, hc, budget_currency=cur).passes]
    v_ret = [r for r in returns if check_flight(r, hc, budget_currency=cur).passes]
    v_hot = [h for h in hotels if check_hotel(h, hc, budget_currency=cur).passes]
    for label, raw, valid in (("outbound flight", outbounds, v_out), ("return flight", returns, v_ret), ("hotel", hotels, v_hot)):
        if len(raw) != len(valid):
            notes.append(f"{len(raw) - len(valid)} {label} option(s) were excluded because they violate your hard constraints.")

    if not outbounds:
        notes.append("No usable outbound flights were returned by the flight provider.")
    if needs_return and not returns:
        notes.append("No usable return flights were returned by the flight provider.")
    if not hotels:
        notes.append("No hotels covering the requested stay were returned by the hotel provider.")

    r_out, r_ret, r_hot = _rank_flights(v_out), _rank_flights(v_ret), _rank_hotels(v_hot, nights)

    def alts(sel_out, sel_ret, sel_hot):
        return (
            [o for o in r_out if sel_out is None or o.option_id != sel_out.option_id][:2],
            [o for o in r_ret if sel_ret is None or o.option_id != sel_ret.option_id][:2] if needs_return else [],
            [o for o in r_hot if sel_hot is None or o.hotel_id != sel_hot.hotel_id][:3],
        )

    # Partial results: at least one component is missing, so a complete package cannot be built.
    if not r_out or not r_hot or (needs_return and not r_ret):
        if not (r_out or r_ret or r_hot):
            notes.append("No packages could be built from the provider results.")
            return [], notes
        so, sr, sh = (r_out[0] if r_out else None), (r_ret[0] if r_ret and needs_return else None), (r_hot[0] if r_hot else None)
        ao, ar, ah = alts(so, sr, sh)
        pkg = _compose(
            pkg_id="package-1", name="Package 1: Partial Results",
            desc="Incomplete package: one or more components were not available from the provider results.",
            tier="incomplete", ts=ts, base_day_wise=base_day_wise, base_summary=base_trip_summary,
            out=so, ret=sr, hotel=sh, out_alts=ao, ret_alts=ar, h_alts=ah, hotel_names=names,
        )
        notes.append("Only a partial package could be built; it is not a complete or booking-ready trip.")
        return [pkg], notes

    ret_choices: list[FlightOption | None] = list(_shortlist(r_ret, _score_flight, _flight_price, lambda o: o.option_id)) if needs_return else [None]
    cands: list[Candidate] = []
    for o in _shortlist(r_out, _score_flight, _flight_price, lambda o: o.option_id):
        for r in ret_choices:
            for h in _shortlist(r_hot, _score_hotel, lambda x: hotel_cost_item(x, nights).amount or _BIG, lambda x: x.hotel_id):
                cands.append(Candidate(
                    out=o, ret=r, hotel=h, pb=calculate_package_budget(ts, o, r, h),
                    score=_score_flight(o) + (_score_flight(r) if r else 0.0) + _score_hotel(h),
                ))

    within = [c for c in cands if c.pb.classification == BudgetClassification.WITHIN_BUDGET]
    over = [c for c in cands if c.pb.classification == BudgetClassification.OVER_BUDGET]
    other = [c for c in cands if c.pb.classification in (BudgetClassification.INCOMPLETE, BudgetClassification.NO_BUDGET)]

    if within:
        plan = [
            ("Optimal Value", "Highest combined flight + hotel score among combinations that fit the budget.", "within_budget", within, _key_value),
            ("Top-Rated Stay", "Highest-rated hotel not used in an earlier package, among combinations that fit the budget.", "within_budget", within, _key_quality),
            ("Lowest Cost", "Lowest total among combinations that fit the budget, preferring a hotel not used in an earlier package.", "within_budget", within, _key_economy),
            ("Premium Upgrade", "Highest combined score among combinations above the requested budget.", "over_budget", over, _key_value),
        ]
        if not over:
            notes.append("No combination above the requested budget could be formed from the provider results, so no over-budget package is included.")
    elif over:
        notes.append("Every available combination exceeds the requested budget; the packages below are all above budget.")
        plan = [
            ("Closest to Budget", "Lowest total among available combinations; all exceed the requested budget.", "over_budget", over, _key_economy),
            ("Best Value (Over Budget)", "Highest combined score among available combinations; all exceed the requested budget.", "over_budget", over, _key_value),
            ("Top-Rated Stay (Over Budget)", "Highest-rated hotel not used in an earlier package; all exceed the requested budget.", "over_budget", over, _key_quality),
            ("Premium (Over Budget)", "Next-highest combined score; all available combinations exceed the requested budget.", "over_budget", over, _key_value),
        ]
    elif other:
        notes.append(
            "Package totals could not be classified against the budget because some prices are unknown "
            "(for example, the provider does not state whether flight prices cover one or all travelers), or no budget was given."
        )
        plan = [
            ("Highest Score", "Highest combined flight + hotel score; budget status unknown.", "unclassified", other, _key_value),
            ("Top-Rated Stay", "Highest-rated hotel not used in an earlier package; budget status unknown.", "unclassified", other, _key_quality),
            ("Lowest Known Price", "Lowest known price, preferring a hotel not used earlier; budget status unknown.", "unclassified", other, _key_economy),
            ("Alternative Combination", "Next-highest combined score; budget status unknown.", "unclassified", other, _key_value),
        ]
    else:
        notes.append("No valid flight and hotel combination could be formed from the provider results.")
        return [], notes

    chosen: list[Candidate] = []
    packages: list[TravelPackage] = []
    for role, desc, tier, pool, key in plan:
        c = _pick(pool, chosen, key)
        if c is None:
            continue
        chosen.append(c)
        n = len(packages) + 1
        ao, ar, ah = alts(c.out, c.ret, c.hotel)
        packages.append(_compose(
            pkg_id=f"package-{n}", name=f"Package {n}: {role}", desc=desc, tier=tier, ts=ts,
            base_day_wise=base_day_wise, base_summary=base_trip_summary,
            out=c.out, ret=c.ret, hotel=c.hotel, out_alts=ao, ret_alts=ar, h_alts=ah, hotel_names=names,
        ))

    n_within = sum(1 for p in packages if p.budget_classification == BudgetClassification.WITHIN_BUDGET)
    if within and n_within < 3:
        notes.append(f"Provider results supported only {n_within} distinct within-budget package(s).")
    if len({p.selected_hotel.hotel_id for p in packages if p.selected_hotel}) < len(packages):
        notes.append("Some packages share the same hotel because the provider returned too few distinct hotels.")
    if len(packages) < 4:
        notes.append(f"Only {len(packages)} of the 4 targeted packages could be built from the available provider results.")
    return packages, notes
