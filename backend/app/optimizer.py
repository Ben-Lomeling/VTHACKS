"""Chain optimizer. Owner: Nischal.

STUB (Phase 0): returns one fake chain built from the first loads it's given. Real DFS lands in Phase 2.
"""
from datetime import datetime, timedelta

from app.models import Chain, Load, Place, TruckProfile
from app.profit import evaluate_load

STATUS = "stub"


def best_chains(profile: TruckProfile, start: Place, start_time: datetime, loads: list[Load], top_k: int = 3) -> list[Chain]:
    picked = loads[:3]
    if not picked:
        return []
    legs = [evaluate_load(l, profile, 100.0, 500.0) for l in picked]
    schedule = []
    t = start_time
    for l in picked:
        schedule.append({
            "load_id": l.id,
            "depart_at": t.isoformat(),
            "pickup_at": (t + timedelta(hours=2)).isoformat(),
            "delivered_at": (t + timedelta(hours=14)).isoformat(),
        })
        t += timedelta(hours=24)
    total = sum(x.net_profit for x in legs) - 95.0
    return [Chain(
        loads=[l.id for l in picked], legs=legs,
        home_deadhead_miles=120.0, home_deadhead_cost=95.0,
        total_net_profit=total, total_miles=sum(x.total_miles for x in legs) + 120.0,
        days=3.5, net_per_day=total / 3.5, ends_at=picked[-1].destination,
        feasible_notes=[f"10-h rest inserted before {picked[-1].id}"], schedule=schedule,
    )][:top_k]
