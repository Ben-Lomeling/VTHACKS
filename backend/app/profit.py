"""Profit math — pure functions, no I/O. Owner: Nischal.

STUB (Phase 0): returns the SPEC golden example numbers for any load. Real math lands in Phase 1.
"""
from app.models import Load, LoadEconomics, TruckProfile

STATUS = "stub"


def evaluate_load(load: Load, profile: TruckProfile, deadhead_miles: float, loaded_miles: float) -> LoadEconomics:
    return LoadEconomics(
        load_id=load.id, deadhead_miles=100.0, loaded_miles=500.0, total_miles=600.0,
        posted_rpm=2.40, fuel_cost=342.97, variable_cost=120.0, fixed_cost=300.0,
        dispatch_fee=120.0, net_profit=317.03, true_net_cpm=0.5284,
        break_even_rate=847.75, counter_offer_rate=1347.75, verdict="negotiate",
    )
