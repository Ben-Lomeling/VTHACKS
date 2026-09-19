"""Chain optimizer: find the best 1-3 load runs that end near home. Owner: Nischal.

How it works (the 30-second version for judges):
  1. Start the truck at its current location and time, with a fresh 11-hour driving clock.
  2. Depth-first search: try every compatible load as leg 1, then every load that can follow it
     as leg 2, then leg 3. Every partial run is also a candidate (1, 2 or 3 loads).
  3. Each step simulates the clock for real: drive empty to pickup, wait if early for the pickup
     window, 2 h loading, drive loaded, 2 h unloading. Simplified hours of service: after 11 h of
     driving we insert a 10 h rest (splitting a long drive if needed); a wait of 10 h+ counts as a rest.
  4. Pruning cuts dead branches early: wrong trailer type, load already used, more than 250 empty
     miles to pickup, arriving after the pickup window closes, or delivering after the deadline.
  5. Score = sum of each leg's net profit (profit.py) minus the cost of the empty drive home.
     We keep runs that end within 150 mi of home, and return the top 3 that each start with a
     different load, so the driver sees three real alternatives, not one run three ways.
     Profitable runs always come first. If fewer than 3 exist, runs that LOSE money (and still end within
     150 mi of home) fill the leftover slots, flagged `losing: true` with a one-line reason, so the driver
     sees why nothing nearby pays instead of an empty screen.
  With 60 loads, depth 3 and the 250-mile prune this is a few thousand steps: well under a second.

Pure: no network, no files. Places must already have lat/lng (main.py resolves them first).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.geo import distance_miles, drive_hours
from app.models import Chain, Load, LoadEconomics, Place, TruckProfile
from app.profit import evaluate_load

STATUS = "live"

MAX_DEPTH = 3
MAX_DEADHEAD_MI = 250.0
HOME_RADIUS_MI = 150.0
MAX_DRIVE_H = 11.0
REST_H = 10.0
LOAD_H = 2.0
UNLOAD_H = 2.0


@dataclass(frozen=True)
class Clock:
    """Where the truck's day stands: current time and driving hours since the last 10-h rest."""
    t: datetime
    driven: float = 0.0


def _drive(clock: Clock, hours: float, what: str) -> tuple[Clock, list[str]]:
    """Advance the clock by a drive, inserting 10-h rests whenever the 11-h limit would be passed."""
    t, driven, notes = clock.t, clock.driven, []
    remaining = hours
    while driven + remaining > MAX_DRIVE_H + 1e-9:
        chunk = MAX_DRIVE_H - driven          # drive until the limit (may be 0), then rest
        t += timedelta(hours=chunk + REST_H)
        remaining -= chunk
        driven = 0.0
        notes.append(f"10-h rest inserted {what}")
    return Clock(t + timedelta(hours=remaining), driven + remaining), notes


def _wait_until(clock: Clock, when: datetime | None, load_id: str) -> tuple[Clock, list[str]]:
    """Wait for a pickup window to open. A wait of 10 h or more counts as the rest."""
    if when is None or clock.t >= when:
        return clock, []
    hours = (when - clock.t).total_seconds() / 3600
    driven = 0.0 if hours >= REST_H else clock.driven
    return Clock(when, driven), [f"Waited {hours:.1f} h for pickup window at {load_id}"]


@dataclass(frozen=True)
class _Leg:
    load: Load
    econ: LoadEconomics
    depart_at: datetime
    pickup_at: datetime
    delivered_at: datetime
    notes: tuple[str, ...]


def _try_leg(profile: TruckProfile, pos: Place, clock: Clock, load: Load, loaded_mi: float) -> tuple[_Leg, Clock] | None:
    """Simulate hauling `load` from `pos`. Returns None if any rule makes it infeasible."""
    deadhead = distance_miles(pos, load.origin)
    if deadhead > MAX_DEADHEAD_MI:
        return None
    depart = clock.t
    clock, notes = _drive(clock, drive_hours(deadhead), f"before pickup of {load.id}")
    if load.pickup_window_end is not None and clock.t > load.pickup_window_end:
        return None
    clock, waited = _wait_until(clock, load.pickup_window_start, load.id)
    pickup_at = clock.t
    clock = Clock(clock.t + timedelta(hours=LOAD_H), clock.driven)
    clock, hauled = _drive(clock, drive_hours(loaded_mi), f"while hauling {load.id}")
    if load.delivery_by is not None and clock.t > load.delivery_by:
        return None
    clock = Clock(clock.t + timedelta(hours=UNLOAD_H), clock.driven)
    try:
        econ = evaluate_load(load, profile, deadhead, loaded_mi)
    except ValueError:
        return None
    return _Leg(load, econ, depart, pickup_at, clock.t, tuple(notes + waited + hauled)), clock


def home_cost_per_mile(profile: TruckProfile) -> float:
    """Empty miles home: empty-mpg fuel + maintenance + fixed cost per mile (no pay, no dispatch fee)."""
    return profile.fuel_price / profile.mpg_empty + profile.variable_cpm + profile.fixed_monthly / profile.miles_per_month


def _finish(profile: TruckProfile, start_time: datetime, legs: list[_Leg], clock: Clock) -> Chain:
    end = legs[-1].load.destination
    home_mi = distance_miles(end, profile.home)
    home_clock, home_notes = _drive(clock, drive_hours(home_mi), "on the drive home")
    home_cost = home_mi * home_cost_per_mile(profile)
    total = sum(l.econ.net_profit for l in legs) - home_cost
    days = (home_clock.t - start_time).total_seconds() / 86400
    return Chain(
        loads=[l.load.id for l in legs],
        legs=[l.econ for l in legs],
        home_deadhead_miles=home_mi,
        home_deadhead_cost=home_cost,
        total_net_profit=total,
        total_miles=sum(l.econ.total_miles for l in legs) + home_mi,
        days=days,
        net_per_day=total / days if days > 0 else total,
        ends_at=end,
        feasible_notes=[n for l in legs for n in l.notes] + home_notes,
        schedule=[{
            "load_id": l.load.id,
            "depart_at": l.depart_at.isoformat(),
            "pickup_at": l.pickup_at.isoformat(),
            "delivered_at": l.delivered_at.isoformat(),
        } for l in legs],
    )


def _usable(load: Load, profile: TruckProfile) -> bool:
    has_coords = None not in (load.origin.lat, load.origin.lng, load.destination.lat, load.destination.lng)
    trailer_ok = load.trailer_type is None or load.trailer_type == profile.trailer_type
    return has_coords and trailer_ok and load.rate_usd > 0


def best_chains(profile: TruckProfile, start: Place, start_time: datetime, loads: list[Load], top_k: int = 3) -> list[Chain]:
    candidates = [l for l in loads if _usable(l, profile)]
    loaded_mi = {l.id: l.loaded_miles_est or distance_miles(l.origin, l.destination) for l in candidates}

    runs: list[Chain] = []

    def dfs(pos: Place, clock: Clock, legs: list[_Leg], used: set[str]) -> None:
        for load in candidates:
            if load.id in used:
                continue
            step = _try_leg(profile, pos, clock, load, loaded_mi[load.id])
            if step is None:
                continue
            leg, after = step
            chain = legs + [leg]
            runs.append(_finish(profile, start_time, chain, after))
            if len(chain) < MAX_DEPTH:
                dfs(load.destination, after, chain, used | {load.id})

    dfs(start, Clock(start_time), [], set())

    profitable = [c for c in runs if c.total_net_profit > 0]
    near_home = [c for c in profitable if c.home_deadhead_miles <= HOME_RADIUS_MI]
    main_pool = near_home or profitable          # no profitable run near home -> best profitable anywhere
    losing = [c for c in runs if c.total_net_profit <= 0 and c.home_deadhead_miles <= HOME_RADIUS_MI]
    main_pool.sort(key=lambda c: (-c.total_net_profit, c.loads))
    losing.sort(key=lambda c: (-c.total_net_profit, c.loads))    # smallest loss first

    picked: list[Chain] = []
    first_loads: set[str] = set()
    for c in main_pool + losing:                 # losing runs only fill slots profitable runs left open
        if len(picked) == top_k:
            break
        if c.loads[0] in first_loads:
            continue
        picked.append(c)
        first_loads.add(c.loads[0])

    for c in picked:
        if c.total_net_profit <= 0:
            c.losing = True
            c.losing_reason = losing_reason(c)
        elif not near_home:
            c.feasible_notes.append(f"No run ends within {HOME_RADIUS_MI:.0f} mi of home; best available shown")
    return picked


def losing_reason(chain: Chain) -> str:
    """One line on why a run loses money, naming the biggest driver: empty miles or low pay."""
    loss = -chain.total_net_profit
    to_pickup = chain.legs[0].deadhead_miles
    empty = sum(l.deadhead_miles for l in chain.legs) + chain.home_deadhead_miles
    share = empty / chain.total_miles if chain.total_miles else 0.0
    if share >= 0.25 and to_pickup >= empty / 2:
        return f"Loses ${loss:,.0f}: {to_pickup:.0f} empty miles to pickup"
    if share >= 0.25:
        return f"Loses ${loss:,.0f}: {empty:.0f} empty miles ({share:.0%} of the run)"
    loaded = sum(l.loaded_miles for l in chain.legs)
    pay_per_mi = sum(l.posted_rpm * l.loaded_miles for l in chain.legs) / loaded
    return f"Loses ${loss:,.0f}: pays only ${pay_per_mi:.2f} per loaded mile"
