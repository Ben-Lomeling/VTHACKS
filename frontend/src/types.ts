export interface Place {
  city: string;
  lat?: number | null;
  lng?: number | null;
}
export interface TruckProfile {
  home: Place;
  current_location: Place;
  trailer_type: "dry_van" | "reefer" | "flatbed";
  mpg_loaded: number;
  mpg_empty: number;
  fuel_price: number;
  variable_cpm: number;
  fixed_monthly: number;
  miles_per_month: number;
  dispatch_pct: number;
  target_net_cpm: number;
  cost_source: "manual" | "nessie";
}
export interface Load {
  id: string;
  origin: Place;
  destination: Place;
  pickup_window_start?: string | null;
  pickup_window_end?: string | null;
  delivery_by?: string | null;
  rate_usd: number;
  loaded_miles_est?: number | null;
  trailer_type?: string | null;
  weight_lbs?: number | null;
  commodity?: string | null;
  broker?: string | null;
  payment_terms_days: number;
  quick_pay_fee_pct: number;
  source: "pasted" | "screenshot" | "simulated";
}
export interface ExtractionResult {
  load: Load;
  confidence: Record<string, "high" | "low">;
  warnings: string[];
}
export interface LoadEconomics {
  load_id: string;
  deadhead_miles: number;
  loaded_miles: number;
  total_miles: number;
  posted_rpm: number;
  fuel_cost: number;
  variable_cost: number;
  fixed_cost: number;
  dispatch_fee: number;
  net_profit: number;
  true_net_cpm: number;
  break_even_rate: number;
  counter_offer_rate: number;
  verdict: "take" | "negotiate" | "skip";
}
export interface Chain {
  loads: string[];
  legs: LoadEconomics[];
  home_deadhead_miles: number;
  home_deadhead_cost: number;
  total_net_profit: number;
  total_miles: number;
  days: number;
  net_per_day: number;
  ends_at: Place;
  feasible_notes: string[];
  schedule: Record<string, unknown>[];
  losing?: boolean;
  losing_reason?: string | null;
}
export interface CashflowCheck {
  starting_balance: number;
  lowest_balance: number;
  lowest_balance_date: string;
  shortfall: boolean;
  quick_pay_fixes_it: boolean;
  quick_pay_cost: number;
  timeline: Record<string, unknown>[];
  later: Record<string, unknown>[];
}
export interface EvaluateRequest {
  load: Load;
}
export interface OffersRequest {
  loads: Load[];
}
export interface ChainsRequest {
  seed_load_ids?: string[];
  include_board?: boolean;
}
export interface CashflowRequest {
  chain: Chain;
}
export interface ExplainRequest {
  economics: LoadEconomics;
  chain?: Chain | null;
  cashflow?: CashflowCheck | null;
}
export interface CounterRequest {
  economics: LoadEconomics;
}
export interface TextResponse {
  text: string;
}
export interface CostsFromBank {
  current: TruckProfile;
  proposed: TruckProfile;
  evidence: Record<string, unknown>;
}
export interface Health {
  modules: Record<string, "stub" | "live" | "fixture">;
  demo_now: string;
  board_loads: number;
  pasted_loads: number;
}
