"""Profit math — pure functions, no I/O. Owner: Nischal.

Formulas are exactly SPEC.md "The math". Full precision internally; round only for display.
"""
from app.models import Load, LoadEconomics, TruckProfile

STATUS = "live"


def evaluate_load(load: Load, profile: TruckProfile, deadhead_miles: float, loaded_miles: float) -> LoadEconomics:
    """What the driver actually keeps on one load, after the empty drive to pickup and every cost."""
    rate = load.rate_usd
    if loaded_miles <= 0:
        raise ValueError(f"loaded_miles must be > 0 for load {load.id}, got {loaded_miles}")
    if rate <= 0:
        raise ValueError(f"rate_usd must be > 0 for load {load.id}, got {rate}")
    if deadhead_miles < 0:
        raise ValueError(f"deadhead_miles can't be negative for load {load.id}, got {deadhead_miles}")

    p = profile
    total_miles = deadhead_miles + loaded_miles
    fuel_cost = p.fuel_price * (deadhead_miles / p.mpg_empty + loaded_miles / p.mpg_loaded)
    variable_cost = p.variable_cpm * total_miles
    fixed_cost = (p.fixed_monthly / p.miles_per_month) * total_miles
    dispatch_fee = rate * p.dispatch_pct
    net_profit = rate - dispatch_fee - fuel_cost - variable_cost - fixed_cost

    costs = fuel_cost + variable_cost + fixed_cost
    keep_share = 1 - p.dispatch_pct  # share of the rate left after the dispatcher's cut
    break_even_rate = costs / keep_share
    counter_offer_rate = (costs + p.target_net_cpm * total_miles) / keep_share
    true_net_cpm = net_profit / total_miles

    # His own rule of thumb on the posted rate ("I only take loads over $3/mi"), kept separate from
    # target_net_cpm, which is what he KEEPS after every cost.
    meets_posted_rule = None if p.min_posted_cpm <= 0 else (rate / loaded_miles) >= p.min_posted_cpm

    if true_net_cpm >= p.target_net_cpm:
        verdict = "take"
    elif counter_offer_rate <= rate * 1.20:
        verdict = "negotiate"
    else:
        verdict = "skip"

    return LoadEconomics(
        load_id=load.id,
        deadhead_miles=deadhead_miles,
        loaded_miles=loaded_miles,
        total_miles=total_miles,
        posted_rpm=rate / loaded_miles,
        fuel_cost=fuel_cost,
        variable_cost=variable_cost,
        fixed_cost=fixed_cost,
        dispatch_fee=dispatch_fee,
        net_profit=net_profit,
        true_net_cpm=true_net_cpm,
        break_even_rate=break_even_rate,
        counter_offer_rate=counter_offer_rate,
        verdict=verdict,
        meets_posted_rule=meets_posted_rule,
    )
