"""optimizer.best_chains: hand-built scenarios where we know the right answer, plus the real board.

Geometry: everything sits on longitude -80, so 1 degree of latitude = 69.09 straight miles
= ~82.9 road miles (x 1.2) = ~1.66 h at 50 mph.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import optimizer
from app.geo import distance_miles
from app.models import Load, Place, TruckProfile
from app.optimizer import Clock, best_chains
from app.profit import evaluate_load

T0 = datetime(2026, 1, 5, 6, 0)
HOME = Place(city="Home, VA", lat=36.0, lng=-80.0)
N2 = Place(city="Two North, VA", lat=38.0, lng=-80.0)       # ~166 road mi from home
N4 = Place(city="Four North, PA", lat=40.0, lng=-80.0)      # ~332 road mi from home
N6 = Place(city="Six North, NY", lat=42.0, lng=-80.0)       # > 250 mi from every other point


def profile(**kw) -> TruckProfile:
    return TruckProfile(home=HOME, current_location=HOME, trailer_type="dry_van", **kw)


def mk(id, origin, dest, rate, **kw) -> Load:
    return Load(id=id, origin=origin, destination=dest, rate_usd=rate, trailer_type="dry_van",
                source="simulated", **kw)


def h(hours: float) -> datetime:
    return T0 + timedelta(hours=hours)


# ---- the 4-load fixture with a known answer ----

def test_four_load_fixture_picks_the_known_best_run():
    A = mk("A", HOME, N2, 1500)       # out...
    B = mk("B", N2, HOME, 1500)       # ...and back: the obvious best, ends at home
    C = mk("C", HOME, N2, 400)        # cheap, and ends far from home unless followed by B
    D = mk("D", N6, HOME, 10_000)     # pays a fortune but pickup is > 250 mi from anywhere -> pruned
    p = profile()
    chains = best_chains(p, HOME, T0, [A, B, C, D])

    best = chains[0]
    assert best.loads == ["A", "B"]
    leg = distance_miles(HOME, N2)
    expected = (evaluate_load(A, p, 0, leg).net_profit + evaluate_load(B, p, 0, leg).net_profit)
    assert best.total_net_profit == pytest.approx(expected)
    assert best.home_deadhead_miles == pytest.approx(0)

    assert all("D" not in c.loads for c in chains), "250-mi deadhead prune failed"
    firsts = [c.loads[0] for c in chains]
    assert len(firsts) == len(set(firsts)), "top chains must start with different loads"
    assert all(c.home_deadhead_miles <= 150 for c in chains)
    assert [c.total_net_profit for c in chains] == sorted((c.total_net_profit for c in chains), reverse=True)


def test_schedule_and_days_add_up():
    A = mk("A", HOME, N2, 1500)
    B = mk("B", N2, HOME, 1500)
    best = best_chains(profile(), HOME, T0, [A, B])[0]
    leg_h = distance_miles(HOME, N2) / 50
    # A: load 2h, drive, unload 2h. B: no deadhead, load 2h, drive, unload 2h. Home: 0 mi.
    assert datetime.fromisoformat(best.schedule[0]["delivered_at"]) == h(2 + leg_h + 2)
    assert datetime.fromisoformat(best.schedule[1]["pickup_at"]) == h(4 + leg_h)
    assert best.days == pytest.approx((8 + 2 * leg_h) / 24)
    assert best.net_per_day == pytest.approx(best.total_net_profit / best.days)


# ---- timing rules: each scenario fails for exactly one reason ----

def test_infeasible_only_because_of_hours_of_service():
    # 600 loaded miles = 12 h of driving. Without HOS: arrive at 2 + 12 = 14 h (deadline 20 h is fine).
    # With HOS: 11 h, a 10-h rest, 1 h -> arrive at 24 h, after the deadline.
    L = mk("H1", HOME, N2, 3000, loaded_miles_est=600, delivery_by=h(20))
    assert best_chains(profile(), HOME, T0, [L]) == []

    ok = mk("H1", HOME, N2, 3000, loaded_miles_est=600, delivery_by=h(30))
    chain = best_chains(profile(), HOME, T0, [ok])[0]
    assert "10-h rest inserted while hauling H1" in chain.feasible_notes
    assert datetime.fromisoformat(chain.schedule[0]["delivered_at"]) == h(24 + 2)


def test_infeasible_only_because_of_pickup_window():
    drive = distance_miles(HOME, N2) / 50            # ~3.3 h to reach pickup
    late = mk("W1", N2, HOME, 1500, pickup_window_end=h(drive - 0.5))
    assert best_chains(profile(), HOME, T0, [late]) == []
    on_time = mk("W1", N2, HOME, 1500, pickup_window_end=h(drive + 0.5))
    assert best_chains(profile(), HOME, T0, [on_time])[0].loads == ["W1"]


def test_arriving_early_waits_for_the_window():
    drive = distance_miles(HOME, N2) / 50
    L = mk("E1", N2, HOME, 1500, pickup_window_start=h(8), pickup_window_end=h(9))
    chain = best_chains(profile(), HOME, T0, [L])[0]
    assert chain.schedule[0]["pickup_at"] == h(8).isoformat()
    assert f"Waited {8 - drive:.1f} h for pickup window at E1" in chain.feasible_notes


def test_a_long_wait_counts_as_rest():
    # Leg 1: 10 h of driving. Leg 2: another 10 h. Normally that needs a rest, but the truck
    # waits 12 h for leg 2's window, which resets the clock, so no rest is inserted.
    L1 = mk("R1", HOME, HOME, 2500, loaded_miles_est=500)
    L2 = mk("R2", HOME, HOME, 2500, loaded_miles_est=500, pickup_window_start=h(2 + 10 + 2 + 12))
    chain = next(c for c in best_chains(profile(), HOME, T0, [L1, L2]) if c.loads == ["R1", "R2"])
    assert "Waited 12.0 h for pickup window at R2" in chain.feasible_notes
    assert not any("rest" in n for n in chain.feasible_notes)


def test_drive_splits_at_eleven_hours():
    clock, notes = optimizer._drive(Clock(T0, driven=9.0), 5.0, "before X")
    # 2 h to hit 11, rest 10, then 3 more
    assert clock.t == h(2 + 10 + 3) and clock.driven == 3.0
    assert notes == ["10-h rest inserted before X"]
    clock, notes = optimizer._drive(Clock(T0), 25.0, "x")
    assert len(notes) == 2 and clock.t == h(25 + 20) and clock.driven == 3.0


def test_short_wait_does_not_reset_the_clock():
    clock, _ = optimizer._wait_until(Clock(T0, driven=8.0), h(3), "X")
    assert clock.driven == 8.0
    clock, _ = optimizer._wait_until(Clock(T0, driven=8.0), h(10), "X")
    assert clock.driven == 0.0


# ---- filters and fallbacks ----

def test_trailer_type_and_reuse():
    reefer = mk("F1", HOME, N2, 5000).model_copy(update={"trailer_type": "reefer"})
    ok = mk("F2", HOME, HOME, 900, loaded_miles_est=200)
    chains = best_chains(profile(), HOME, T0, [reefer, ok])
    assert all("F1" not in c.loads for c in chains)
    assert all(len(c.loads) == len(set(c.loads)) for c in chains)


def test_no_run_near_home_returns_best_with_note():
    far = mk("X1", HOME, N4, 3000)          # ends ~332 mi from home
    chains = best_chains(profile(), HOME, T0, [far])
    assert chains[0].loads == ["X1"]
    assert "No run ends within 150 mi of home; best available shown" in chains[0].feasible_notes


def test_real_board_runs_under_one_second():
    data = Path(__file__).resolve().parents[1] / "data"
    board = [Load.model_validate(x) for x in json.loads((data / "seed_loads.json").read_text())["loads"]]
    p = TruckProfile.model_validate_json((data / "profile.json").read_text())
    for trailer in ("dry_van", "reefer", "flatbed"):
        prof = p.model_copy(update={"trailer_type": trailer})
        started = time.perf_counter()
        chains = best_chains(prof, prof.current_location, datetime(2026, 9, 21, 6), board)
        assert time.perf_counter() - started < 1.0
        assert len(chains) <= 3


def test_losing_run_fills_an_empty_slot_with_a_reason():
    bad = mk("M1", HOME, HOME, 50, loaded_miles_est=300)          # pays $50 for 300 mi
    chains = best_chains(profile(), HOME, T0, [bad])
    assert [c.loads for c in chains] == [["M1"]]
    c = chains[0]
    assert c.losing is True and c.total_net_profit < 0
    assert c.losing_reason == f"Loses ${-c.total_net_profit:,.0f}: pays only $0.17 per loaded mile"


def test_losing_runs_rank_below_profitable_and_only_fill_leftover_slots():
    # Windows close early, so a bad load (10 h) can't be followed by a good one to make it profitable.
    good = mk("G1", HOME, N2, 1500, pickup_window_end=h(1))
    back = mk("G2", N2, HOME, 1500, pickup_window_end=h(9))
    bad1 = mk("B1", HOME, HOME, 50, loaded_miles_est=300)
    bad2 = mk("B2", HOME, HOME, 60, loaded_miles_est=300)
    chains = best_chains(profile(), HOME, T0, [good, back, bad1, bad2])
    flags = [c.losing for c in chains]
    assert flags == sorted(flags), "profitable runs must come before losing runs"
    assert len(chains) == 3
    profitable = [c for c in chains if not c.losing]
    assert {c.loads[0] for c in profitable} == {"G1", "G2"}
    assert chains[2].loads == ["B2"], "the smaller loss fills the one leftover slot"
    assert all(c.losing_reason is None for c in profitable)


def test_no_losing_runs_when_three_profitable_exist():
    loads = [mk(f"P{i}", HOME, HOME, 2000, loaded_miles_est=300) for i in range(3)]
    loads.append(mk("B1", HOME, HOME, 50, loaded_miles_est=300))
    chains = best_chains(profile(), HOME, T0, loads)
    assert len(chains) == 3 and not any(c.losing for c in chains)


def test_losing_runs_far_from_home_are_not_shown():
    far_bad = mk("FB", HOME, N4, 100)            # loses money and ends ~332 mi from home
    assert best_chains(profile(), HOME, T0, [far_bad]) == []


def test_losing_reason_names_empty_miles_to_pickup():
    # pickup ~166 empty miles away, then a short cheap haul home
    L = mk("E1", N2, HOME, 150, loaded_miles_est=60)
    c = best_chains(profile(), HOME, T0, [L])[0]
    assert c.losing and c.losing_reason.endswith("166 empty miles to pickup")


def test_every_run_reports_days_and_net_per_day():
    loads = [mk("A", HOME, N2, 1500), mk("B", N2, HOME, 1500), mk("M1", HOME, HOME, 50, loaded_miles_est=300)]
    for c in best_chains(profile(), HOME, T0, loads):
        assert c.days > 0
        assert c.net_per_day == pytest.approx(c.total_net_profit / c.days)
