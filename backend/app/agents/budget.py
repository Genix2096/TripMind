from app.models.flights import FlightOption
from app.models.hotels import HotelOption
from app.models.trip import TripState
from app.planning.budget import (
    BudgetReport,
    CostItem,
    evaluate_budget,
    flight_cost_item,
    hotel_cost_item,
)
from app.planning.constraints import ConstraintReport, check_flight, check_hotel


class BudgetAndConstraintValidationAgent:
    """Agent 7: Budget and Constraint Validation Agent
    
    This agent uses deterministic Python calculations for budget validation and hard constraints,
    as required by the prompt. It does not use the LLM.
    """
    
    def evaluate(
        self,
        state: TripState,
        selected_flight: FlightOption | None,
        selected_hotel: HotelOption | None,
    ) -> tuple[BudgetReport, ConstraintReport, ConstraintReport]:
        
        # 1. Budget Evaluation
        costs: list[CostItem] = []
        if selected_flight:
            costs.append(flight_cost_item(selected_flight, state.travelers.total))
        if selected_hotel:
            costs.append(hotel_cost_item(selected_hotel, state.nights or 0))
            
        budget_report = evaluate_budget(state.budget, state.travelers.total, costs)
        
        # 2. Hard Constraints Evaluation
        flight_constraints = ConstraintReport()
        hotel_constraints = ConstraintReport()
        
        if selected_flight:
            flight_constraints = check_flight(
                selected_flight,
                state.hard_constraints,
                budget_currency=state.budget.currency if state.budget else None
            )
            
        if selected_hotel:
            hotel_constraints = check_hotel(
                selected_hotel,
                state.hard_constraints,
                budget_currency=state.budget.currency if state.budget else None
            )
            
        return budget_report, flight_constraints, hotel_constraints
