export type BudgetClassification = 'within_budget' | 'over_budget' | 'incomplete' | 'no_budget';

export interface Money {
  amount: number | string;
  currency: string;
}

export interface Airport {
  name?: string;
  code?: string;
  local_time?: string;
}

export interface FlightSegment {
  airline?: string;
  flight_number?: string;
  aircraft?: string;
  travel_class?: string;
  departure: Airport;
  arrival: Airport;
  duration_minutes?: number;
  overnight?: boolean;
}

export interface Layover {
  airport_name?: string;
  airport_code?: string;
  duration_minutes?: number;
  overnight?: boolean;
}

export interface FlightOption {
  option_id: string;
  direction?: 'outbound' | 'return' | null;
  segments: FlightSegment[];
  layovers?: Layover[];
  total_duration_minutes?: number;
  stops?: number;
  price?: Money;
  trip_type?: string;
  provider_ranked_best?: boolean;
  departure_token?: string;
  airline_logo?: string;
  missing_fields?: string[];
}

export interface HotelPrice {
  amount?: Money;
  display_text?: string;
}

export interface HotelOption {
  hotel_id: string;
  name?: string;
  property_type?: string;
  description?: string;
  address?: string;
  hotel_class?: number;
  rating?: number;
  review_count?: number;
  amenities?: string[];
  images?: string[];
  check_in_time?: string;
  check_out_time?: string;
  nightly_rate?: HotelPrice;
  total_rate?: HotelPrice;
  link?: string;
}

export interface Activity {
  name: string;
  location?: string;
  description?: string;
  time_window?: string;
  estimated_duration?: string;
  travel_info?: string;
  data_source?: string;
}

export interface DayPlan {
  date?: string;
  title: string;
  activities: Activity[];
  locations?: string[];
  weather_summary?: string;
  scheduling_conflicts?: string[];
  missing_information?: string[];
}

export interface CostItem {
  category: string;
  label: string;
  amount?: number | string;
  currency?: string;
  cost_class: string;
  basis: string;
}

export interface BudgetReport {
  status: string;
  budget_limit?: Money;
  items: CostItem[];
  known_subtotal?: Money;
  missing_categories?: string[];
  currency_mismatches?: CostItem[];
  remaining_after_known_costs?: Money;
  remaining_is_final?: boolean;
  notes?: string[];
}

export type TripPace = 'RUSHED' | 'BALANCED' | 'SLOW';

export interface StructuredTripPace {
  pace: TripPace;
  preference_source: 'explicitly_stated' | 'default_balanced' | 'inferred' | string;
  raw_pace_phrase?: string;
  summary_label?: string;
  description?: string;
}

export interface TravelPackage {
  package_id: string;
  name: string;
  description: string;
  target_tier: 'within_budget' | 'over_budget' | string;
  budget_classification: BudgetClassification;
  selected_outbound_flight?: FlightOption | null;
  selected_return_flight?: FlightOption | null;
  selected_hotel?: HotelOption | null;
  outbound_flight_alternatives: FlightOption[];
  return_flight_alternatives: FlightOption[];
  hotel_alternatives: HotelOption[];
  day_wise: DayPlan[];
  trip_summary: string;
  budget_report: BudgetReport;
  total_cost?: Money | null;
  known_subtotal?: Money | null;
  remaining_budget?: Money | null;
  amount_over_budget?: Money | null;
  currency: string;
  is_complete: boolean;
  completeness_status?: string;
  warnings: string[];
  missing_items?: string[];
  provenance_summary?: Record<string, any>;
  trip_pace?: TripPace;
  pace_description?: string;
}

export interface ProviderResultStatus {
  capability: string;
  status: string;
  error_detail?: string;
}

export interface SeasonalWeatherEstimate {
  status: 'forecast_available' | 'forecast_unavailable_seasonal_available' | 'forecast_and_seasonal_unavailable' | string;
  destination: string;
  travel_month?: string;
  season_name?: string;
  typical_temp_min_c?: number;
  typical_temp_max_c?: number;
  precipitation_context?: string;
  seasonal_caveats?: string[];
  data_source?: string;
  reference_period?: string;
  disclaimer?: string;
  notes?: string[];
}

export interface StructuredItinerary {
  trip_summary: string;
  flights: FlightOption[];
  hotels: HotelOption[];
  day_wise: DayPlan[];
  budget_report?: any;
  provider_statuses?: Record<string, ProviderResultStatus>;
  validation_warnings?: string[];
  packages?: TravelPackage[];
  package_notes?: string[];
  seasonal_weather?: SeasonalWeatherEstimate;
}

export interface StructuredAttractionPreferences {
  primary_interests?: string[];
  secondary_interests?: string[];
  preference_source?: 'explicitly_stated' | 'default_balanced' | string;
  raw_interest_phrases?: string[];
  summary_label?: string;
}

export interface TripPreferences {
  interests?: string[];
  attraction_preferences?: StructuredAttractionPreferences;
  hotel_category?: string;
  food_preferences?: string[];
  pace?: TripPace | string;
  pace_preferences?: StructuredTripPace;
}

export interface TripState {
  raw_request?: string;
  origin?: string;
  destination?: string;
  departure_date?: string;
  return_date?: string;
  calendar_days?: number;
  nights?: number;
  budget?: { amount: number; currency: string; basis: string };
  preferences?: TripPreferences;
  clarification_question?: string;
}
