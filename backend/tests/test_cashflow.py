"""cashflow.simulate: the mid-trip truck-payment dip, the Capital One advance fix, and edge cases. Pure, no network."""
from datetime import date

import pytest

from app.cashflow import _events, home_date, simulate
from app.models import Chain, Load, Place, TruckProfile
from app.profit import evaluate_load

TODAY = date(2026, 9, 21)
RIC = Place(city="Richmond, VA", lat=37.5407, lng=-77.436)
CLT = Place(city="Charlotte, NC", lat=35.2271, lng=-80.8431)
PROFILE = TruckProfile(home=RIC, current_location=RIC, trailer_type="dry_van")
BILLS = [
    {"payee": "Truck payment", "amount": 2150.0, "due_date": date(2026, 10, 1)},
    {"payee": "Truck insurance", "amount": 1100.0, "due_date": date(2026, 10, 5)},
]


def load(id, rate, broker="Blue Ridge Logistics") -> Load:
    return Load(id=id, origin=RIC, destination=CLT, rate_usd=rate, broker=broker,
                payment_terms_days=30, quick_pay_fee_pct=0.03, source="simulated")


def chain_of(*stops) -> tuple[Chain, dict[str, Load]]:
    """stops: (Load, pickup ISO, delivered ISO). Golden economics per leg: fuel $342.97, dispatch 10%."""
    legs = [evaluate_load(l, PROFILE, 100, 500) for l, _, _ in stops]
    chain = Chain(
        loads=[l.id for l, _, _ in stops], legs=legs, home_deadhead_miles=0, home_deadhead_cost=0,
        total_net_profit=sum(x.net_profit for x in legs), total_miles=600 * len(legs), days=3,
        net_per_day=1, ends_at=RIC, feasible_notes=[],
        schedule=[{"load_id": l.id, "depart_at": p, "pickup_at": p, "delivered_at": d} for l, p, d in stops],
    )
    return chain, {l.id: l for l, _, _ in stops}


def test_truck_payment_mid_trip_dips_negative_and_one_advance_fixes_it():
    chain, loads = chain_of(
        (load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"),
        (load("L2", 1200), "2026-09-24T08:00:00", "2026-09-25T06:00:00"),
    )
    # 2,700 - 342.97 (Sep 22), then Sep 24: -342.97 diesel and the 2,150 truck payment -> -135.94
    mid_trip = [{"payee": "Truck payment", "amount": 2150.0, "due_date": date(2026, 9, 24)}]
    cf = simulate(chain, loads, 2700.0, mid_trip, TODAY)
    assert cf.shortfall is True
    assert cf.lowest_balance_date == date(2026, 9, 24)
    assert cf.lowest_balance == pytest.approx(2700 - 2 * 342.97 - 2150, abs=0.02)
    # advance on L1 alone (earliest delivery): +1,080 - 36 fee on its delivery day (Sep 23) keeps him positive
    assert cf.quick_pay_fixes_it is True
    assert cf.quick_pay_cost == pytest.approx(36.0)


def test_timeline_is_this_trip_only_and_broker_pay_goes_to_later():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    cf = simulate(chain, loads, 5000.0, BILLS, TODAY)
    assert cf.timeline[0] == {"date": "2026-09-21", "label": "Checking balance today", "amount": 0.0, "balance": 5000.0}
    running = 5000.0
    for e in cf.timeline[1:]:
        running += e["amount"]
        assert e["balance"] == pytest.approx(running, abs=0.02)
    # home Sep 25 (depart Sep 22 + 3 days): October bills are next month's runs' problem
    assert [e["label"] for e in cf.timeline] == ["Checking balance today", "Diesel for L1"]
    # pay = rate - 10% dispatch, on delivery (Sep 23) + 30 days, shown but not counted
    assert cf.later == [{"date": "2026-10-23", "label": "Pay for L1 (Blue Ridge Logistics)", "amount": 1080.0}]


def test_home_date_is_first_departure_plus_days():
    chain, _ = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    assert home_date(chain, TODAY) == date(2026, 9, 25)


def test_advance_lands_on_delivery_day_and_is_repaid_when_the_broker_pays():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    events, later = _events(chain, loads, [], TODAY, {"L1"})
    assert events[-1] == (date(2026, 9, 23), "Capital One advance on L1", pytest.approx(1044.0))
    assert later == [(date(2026, 10, 23), "Advance on L1 repaid", -1080.0),
                     (date(2026, 10, 23), "Pay for L1 (Blue Ridge Logistics)", 1080.0)]
    assert sum(a for _, _, a in later) == 0          # net cost of the advance = the fee


def test_no_shortfall_means_no_advance():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    cf = simulate(chain, loads, 10_000.0, BILLS, TODAY)
    assert cf.shortfall is False and cf.quick_pay_fixes_it is False and cf.quick_pay_cost == 0


def test_shortfall_advance_cannot_fix():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    early_bill = [{"payee": "Repair shop", "amount": 5000.0, "due_date": date(2026, 9, 22)}]
    cf = simulate(chain, loads, 100.0, early_bill, TODAY)
    assert cf.shortfall is True and cf.quick_pay_fixes_it is False
    assert cf.lowest_balance_date == date(2026, 9, 22)


def test_money_out_before_money_in_on_the_same_day():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    # the advance would land Sep 23, the same day as the truck payment; the payment is booked first
    same_day = [{"payee": "Truck payment", "amount": 2150.0, "due_date": date(2026, 9, 23)}]
    cf = simulate(chain, loads, 1000.0, same_day, TODAY)
    assert cf.shortfall is True and cf.quick_pay_fixes_it is False
    events, _ = _events(chain, loads, same_day, TODAY, {"L1"})
    assert [label for d, label, _ in events if d == date(2026, 9, 23)] == ["Truck payment", "Capital One advance on L1"]


def test_bills_after_he_is_home_are_ignored_and_string_dates_work():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    bills = [{"payee": "Way later", "amount": 99999, "due_date": "2026-12-01"},
             {"payee": "On the road", "amount": 10, "due_date": "2026-09-24"}]
    cf = simulate(chain, loads, 1000.0, bills, TODAY)
    labels = [e["label"] for e in cf.timeline]
    assert "Way later" not in labels and "On the road" in labels
