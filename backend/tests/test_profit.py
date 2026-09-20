"""profit.evaluate_load: SPEC golden test, edge cases, verdict branches, guards."""
import pytest

from app.models import Load, Place, TruckProfile
from app.profit import evaluate_load

RIC = Place(city="Richmond, VA", lat=37.5407, lng=-77.436)
CLT = Place(city="Charlotte, NC", lat=35.2271, lng=-80.8431)


def profile(**kw) -> TruckProfile:
    return TruckProfile(home=RIC, current_location=RIC, trailer_type="dry_van", **kw)


def load(rate: float = 1200.0) -> Load:
    return Load(id="T1", origin=RIC, destination=CLT, rate_usd=rate, source="pasted")


def test_golden_example_matches_spec():
    e = evaluate_load(load(1200), profile(), deadhead_miles=100, loaded_miles=500)
    expected = {
        "posted_rpm": 2.40, "fuel_cost": 342.97, "variable_cost": 120.00, "fixed_cost": 300.00,
        "dispatch_fee": 120.00, "net_profit": 317.03, "true_net_cpm": 0.5284,
        "break_even_rate": 847.75, "counter_offer_rate": 1347.75,
    }
    for field, want in expected.items():
        assert getattr(e, field) == pytest.approx(want, abs=0.01), field
    assert e.total_miles == 600
    assert e.verdict == "negotiate"


def test_full_precision_is_kept():
    e = evaluate_load(load(1200), profile(), 100, 500)
    assert e.fuel_cost != round(e.fuel_cost, 2)  # not rounded internally


def test_zero_deadhead():
    e = evaluate_load(load(1200), profile(), 0, 500)
    assert e.total_miles == 500
    assert e.fuel_cost == pytest.approx(3.80 * 500 / 6.5)
    assert e.true_net_cpm == pytest.approx(e.net_profit / 500)


def test_self_dispatched_has_no_fee_and_break_even_equals_costs():
    e = evaluate_load(load(1200), profile(dispatch_pct=0), 100, 500)
    assert e.dispatch_fee == 0
    assert e.break_even_rate == pytest.approx(e.fuel_cost + e.variable_cost + e.fixed_cost)
    assert e.net_profit == pytest.approx(1200 - e.break_even_rate)


def test_verdict_take():
    # $2,000 on the same miles clears the $0.75/mi target
    e = evaluate_load(load(2000), profile(), 100, 500)
    assert e.true_net_cpm >= 0.75 and e.verdict == "take"


def test_verdict_negotiate():
    e = evaluate_load(load(1200), profile(), 100, 500)  # counter 1347.75 <= 1440
    assert e.verdict == "negotiate"


def test_verdict_skip():
    # $900: counter 1347.75 > 900 * 1.2 = 1080
    e = evaluate_load(load(900), profile(), 100, 500)
    assert e.verdict == "skip"


@pytest.mark.parametrize("miles", [0, -10])
def test_guard_loaded_miles(miles):
    with pytest.raises(ValueError, match="loaded_miles must be > 0"):
        evaluate_load(load(), profile(), 100, miles)


@pytest.mark.parametrize("rate", [0, -5])
def test_guard_rate(rate):
    with pytest.raises(ValueError, match="rate_usd must be > 0"):
        evaluate_load(load(rate), profile(), 100, 500)


def test_posted_rule_is_reported_but_does_not_change_the_verdict():
    """His own rule ("nothing under $3/mi posted") vs what he actually keeps."""
    with_rule = profile(min_posted_cpm=3.0)
    cheap = evaluate_load(load(1200), with_rule, deadhead_miles=100, loaded_miles=500)   # $2.40/mi posted
    assert cheap.meets_posted_rule is False
    assert cheap.verdict == evaluate_load(load(1200), profile(), deadhead_miles=100, loaded_miles=500).verdict
    rich = evaluate_load(load(1600), with_rule, deadhead_miles=100, loaded_miles=500)    # $3.20/mi posted
    assert rich.meets_posted_rule is True
    assert evaluate_load(load(1200), profile(), deadhead_miles=100, loaded_miles=500).meets_posted_rule is None
