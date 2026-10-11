"""Deterministic budget validation. No LLM, no guessing.

Rules enforced here:
* Every cost carries a classification (verified / calculated / user assumption / estimate / unknown).
* Unknown costs are never treated as zero. A budget is only "within budget" when every expected
  category has a known cost; otherwise the report is INCOMPLETE and lists what is missing.
* "Exceeded" is reported as soon as the *known* subtotal alone exceeds the limit (a lower bound).
* Amounts in a different currency than the budget are never converted or summed.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import Money, Provenance
from app.models.flights import FlightOption, PriceScope
from app.models.hotels import HotelOption
from app.models.trip import Budget


class CostClass(str, Enum):
    VERIFIED_PROVIDER = "verified_provider_price"
    CALCULATED = "calculated_from_verified_prices"
    USER_ASSUMPTION = "user_assumption"
    ESTIMATE = "estimate"
    UNKNOWN = "unknown"


class CostCategory(str, Enum):
    FLIGHTS = "flights"
    ACCOMMODATION = "accommodation"
    LOCAL_TRANSPORT = "local_transport"
    FOOD = "food"
    ATTRACTIONS = "attractions"
    OTHER = "other"


EXPECTED_CATEGORIES: tuple[CostCategory, ...] = (
    CostCategory.FLIGHTS,
    CostCategory.ACCOMMODATION,
    CostCategory.LOCAL_TRANSPORT,
    CostCategory.FOOD,
    CostCategory.ATTRACTIONS,
)


class CostItem(BaseModel):
    category: CostCategory
    label: str
    amount: Decimal | None = None
    currency: str | None = None
    cost_class: CostClass
    basis: str
    source: Provenance | None = None


class BudgetStatus(str, Enum):
    EXCEEDED = "exceeded"
    WITHIN_BUDGET = "within_budget"
    INCOMPLETE = "incomplete_costs_unknown"
    NO_BUDGET = "no_budget_provided"


class BudgetReport(BaseModel):
    status: BudgetStatus
    budget_limit: Money | None = None
    items: list[CostItem]
    known_subtotal: Money | None = None
    missing_categories: list[CostCategory] = Field(default_factory=list)
    currency_mismatches: list[CostItem] = Field(default_factory=list)
    remaining_after_known_costs: Money | None = None
    remaining_is_final: bool = False
    notes: list[str] = Field(default_factory=list)


# ---- Cost item builders -----------------------------------------------------------------


def unknown_item(category: CostCategory, label: str, why: str) -> CostItem:
    return CostItem(category=category, label=label, cost_class=CostClass.UNKNOWN, basis=why)


def user_assumption_item(
    category: CostCategory, label: str, amount: Decimal, currency: str, basis: str
) -> CostItem:
    if amount < 0:
        raise ValueError("amount must not be negative")
    return CostItem(
        category=category,
        label=label,
        amount=amount,
        currency=currency.upper(),
        cost_class=CostClass.USER_ASSUMPTION,
        basis=f"User-provided: {basis}",
    )


def flight_cost_item(
    option: FlightOption | None,
    travelers: int,
    *,
    assumed_scope: PriceScope | None = None,
) -> CostItem:
    """Flight cost from a provider price.

    SerpApi does not say whether `price` covers one traveler or all of them, so for more than one
    traveler the scope must be explicitly assumed by the user; otherwise the cost is UNKNOWN.
    """
    label = "Flights"
    if option is None:
        return unknown_item(CostCategory.FLIGHTS, label, "No flight selected.")
    if option.price is None:
        return unknown_item(CostCategory.FLIGHTS, label, "The provider returned no price for this flight.")
    price = option.price
    if travelers <= 1:
        return CostItem(
            category=CostCategory.FLIGHTS, label=label, amount=price.amount, currency=price.currency,
            cost_class=CostClass.VERIFIED_PROVIDER, source=option.provenance,
            basis="Provider search price for a single traveler. Not a guaranteed fare.",
        )
    provider_stated = option.price_scope != PriceScope.UNSPECIFIED
    scope = option.price_scope if provider_stated else assumed_scope
    if scope is None or scope == PriceScope.UNSPECIFIED:
        return unknown_item(
            CostCategory.FLIGHTS,
            label,
            f"The provider does not say whether {price.amount} {price.currency} covers one traveler "
            f"or all {travelers}; confirm and state the assumption.",
        )
    if scope == PriceScope.TOTAL_ALL_TRAVELERS:
        amount = price.amount
        basis = "Provider price treated as the total for all travelers."
        cls = CostClass.VERIFIED_PROVIDER
    else:
        amount = price.amount * travelers
        basis = f"Provider price per traveler x {travelers} travelers."
        cls = CostClass.CALCULATED
    if not provider_stated:
        basis += " Scope is a user assumption; the provider does not state it."
        cls = CostClass.USER_ASSUMPTION
    return CostItem(
        category=CostCategory.FLIGHTS, label=label, amount=amount, currency=price.currency,
        cost_class=cls, source=option.provenance, basis=basis,
    )


def hotel_cost_item(option: HotelOption | None, nights: int) -> CostItem:
    """Hotel cost. Prefers the provider's own total; never derives a rate from an ambiguous field."""
    label = "Accommodation"
    if option is None:
        return unknown_item(CostCategory.ACCOMMODATION, label, "No hotel selected.")
    total = option.total_rate.amount if option.total_rate else None
    if total is not None:
        return CostItem(
            category=CostCategory.ACCOMMODATION, label=label, amount=total.amount,
            currency=total.currency, cost_class=CostClass.VERIFIED_PROVIDER, source=option.provenance,
            basis="Provider 'total_rate' for the searched stay. Taxes/fees not confirmed unless stated.",
        )
    nightly = option.nightly_rate.amount if option.nightly_rate else None
    if nightly is not None and nights > 0:
        return CostItem(
            category=CostCategory.ACCOMMODATION, label=label, amount=nightly.amount * nights,
            currency=nightly.currency, cost_class=CostClass.CALCULATED, source=option.provenance,
            basis=f"Provider nightly rate x {nights} nights. Provider gave no total; taxes/fees unknown.",
        )
    return unknown_item(
        CostCategory.ACCOMMODATION, label, "The provider returned no usable price for this hotel."
    )


# ---- Evaluation -------------------------------------------------------------------------


def evaluate_budget(
    budget: Budget | None,
    travelers: int,
    items: list[CostItem],
    *,
    expected: tuple[CostCategory, ...] = EXPECTED_CATEGORIES,
) -> BudgetReport:
    limit = Money(amount=budget.total_limit(travelers), currency=budget.currency) if budget else None
    reference = limit.currency if limit else next((i.currency for i in items if i.amount is not None and i.currency), None)

    summed = Decimal(0)
    mismatches: list[CostItem] = []
    known_categories: set[CostCategory] = set()
    for item in items:
        if item.amount is None or item.cost_class == CostClass.UNKNOWN:
            continue
        if reference is None or item.currency != reference:
            mismatches.append(item)
            continue
        summed += item.amount
        known_categories.add(item.category)

    missing = [c for c in expected if c not in known_categories]
    subtotal = Money(amount=summed, currency=reference) if reference else None

    notes: list[str] = []
    if mismatches:
        notes.append("Some costs use a different currency than the budget and were not converted or summed.")
    if missing:
        notes.append("Costs for these categories are unknown and are NOT assumed to be zero.")

    if limit is None:
        status = BudgetStatus.NO_BUDGET
    elif summed > limit.amount:
        status = BudgetStatus.EXCEEDED
        notes.append("The known costs alone already exceed the budget; unknown costs would add to this.")
    elif missing or mismatches:
        status = BudgetStatus.INCOMPLETE
    else:
        status = BudgetStatus.WITHIN_BUDGET

    remaining = (
        Money(amount=limit.amount - summed, currency=limit.currency) if limit is not None else None
    )
    return BudgetReport(
        status=status,
        budget_limit=limit,
        items=items,
        known_subtotal=subtotal,
        missing_categories=missing,
        currency_mismatches=mismatches,
        remaining_after_known_costs=remaining,
        remaining_is_final=status == BudgetStatus.WITHIN_BUDGET,
        notes=notes,
    )
