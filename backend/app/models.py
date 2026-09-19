"""Every Pydantic model in SPEC.md. Owner: Nischal. Change only via SPEC.md first."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# ---- Core models (SPEC.md "Data models") ----

class Place(BaseModel):
    city: str            # "Richmond, VA" — always "City, ST"
    lat: float | None = None
    lng: float | None = None


class TruckProfile(BaseModel):
    home: Place
    current_location: Place
    trailer_type: Literal["dry_van", "reefer", "flatbed"]
    mpg_loaded: float = 6.5
    mpg_empty: float = 7.5
    fuel_price: float = 3.80          # $/gal; overwritten by Nessie-derived value when available
    variable_cpm: float = 0.20        # maintenance + tires, $/mile
    fixed_monthly: float = 5000       # truck payment + insurance + permits, $/month
    miles_per_month: float = 10000
    dispatch_pct: float = 0.10        # 0 if self-dispatched
    target_net_cpm: float = 0.75      # driver's minimum acceptable net $/mile
    cost_source: Literal["manual", "nessie"] = "manual"


class Load(BaseModel):
    id: str
    origin: Place
    destination: Place
    pickup_window_start: datetime | None = None
    pickup_window_end: datetime | None = None
    delivery_by: datetime | None = None
    rate_usd: float                    # TOTAL linehaul pay for the load
    loaded_miles_est: float | None = None  # if missing, computed by geo.py
    trailer_type: str | None = None
    weight_lbs: int | None = None
    commodity: str | None = None
    broker: str | None = None
    payment_terms_days: int = 30
    quick_pay_fee_pct: float = 0.03
    source: Literal["pasted", "screenshot", "simulated"]


class ExtractionResult(BaseModel):
    load: Load
    confidence: dict[str, Literal["high", "low"]]  # per field
    warnings: list[str]    # e.g. "Rate may be per-mile, not total", "State missing for Springfield"


class LoadEconomics(BaseModel):
    load_id: str
    deadhead_miles: float
    loaded_miles: float
    total_miles: float
    posted_rpm: float          # rate / loaded_miles  (what the broker advertises)
    fuel_cost: float
    variable_cost: float
    fixed_cost: float
    dispatch_fee: float
    net_profit: float
    true_net_cpm: float        # net / total_miles  (what the driver actually keeps)
    break_even_rate: float
    counter_offer_rate: float  # rate needed to hit target_net_cpm
    verdict: Literal["take", "negotiate", "skip"]


class Chain(BaseModel):
    loads: list[str]              # load ids in order
    legs: list[LoadEconomics]
    home_deadhead_miles: float
    home_deadhead_cost: float
    total_net_profit: float       # sum of legs minus home deadhead cost
    total_miles: float
    days: float                   # start_time -> arrival back home (incl. rests and home deadhead)
    net_per_day: float
    ends_at: Place
    feasible_notes: list[str]     # e.g. "10-hr rest inserted before L014"
    schedule: list[dict]          # [{load_id, depart_at, pickup_at, delivered_at}] ISO strings; cashflow uses delivered_at


class CashflowCheck(BaseModel):
    starting_balance: float
    lowest_balance: float
    lowest_balance_date: date
    shortfall: bool               # lowest_balance < 0
    quick_pay_fixes_it: bool
    quick_pay_cost: float
    timeline: list[dict]          # [{date, label, amount, balance}] for the chart


# ---- Request / response bodies for the API table ----

class EvaluateRequest(BaseModel):
    load: Load


class OffersRequest(BaseModel):
    loads: list[Load]


class ChainsRequest(BaseModel):
    seed_load_ids: list[str] = []
    include_board: bool = True


class CashflowRequest(BaseModel):
    chain: Chain


class ExplainRequest(BaseModel):
    economics: LoadEconomics
    chain: Chain | None = None
    cashflow: CashflowCheck | None = None


class CounterRequest(BaseModel):
    economics: LoadEconomics


class TextResponse(BaseModel):
    text: str


class CostsFromBank(BaseModel):
    current: TruckProfile
    proposed: TruckProfile
    evidence: dict
