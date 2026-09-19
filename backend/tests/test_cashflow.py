"""cashflow.simulate: the mid-trip truck-payment dip, the Capital One advance fix, and edge cases. Pure, no network."""
from datetime import date, datetime

import pytest

from app.cashflow import _events, balance_along_route, home_date, simulate
from app.models import Chain, Load, Place, TruckProfile
from app.profit import evaluate_load

TODAY = date(2026, 9, 21)
RIC = Place(city="Richmond, VA", lat=37.5407, lng=-77.436)
CLT = Place(city="Charlotte, NC", lat=35.2271, lng=-80.8431)
RDU = Place(city="Raleigh, NC", lat=35.7796, lng=-78.6382)
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
    assert events[-1] == (datetime(2026, 9, 23, 10), "Capital One advance on L1", pytest.approx(1044.0), "advance")
    assert [(w.date(), label, amount) for w, label, amount, _ in later] == [
        (date(2026, 10, 23), "Advance on L1 repaid", -1080.0),
        (date(2026, 10, 23), "Pay for L1 (Blue Ridge Logistics)", 1080.0)]
    assert sum(e[2] for e in later) == 0             # net cost of the advance = the fee


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
    assert [e[1] for e in events if e[0].date() == date(2026, 9, 23)] == ["Truck payment", "Capital One advance on L1"]


def test_bills_after_he_is_home_are_ignored_and_string_dates_work():
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"))
    bills = [{"payee": "Way later", "amount": 99999, "due_date": "2026-12-01"},
             {"payee": "On the road", "amount": 10, "due_date": "2026-09-24"}]
    cf = simulate(chain, loads, 1000.0, bills, TODAY)
    labels = [e["label"] for e in cf.timeline]
    assert "Way later" not in labels and "On the road" in labels


# ---- Feature A: money on the map ----
def two_load_trip():
    """L1 RIC->CLT (Sep 22-23), L2 RDU->CLT (Sep 24-25 6 AM), home Sep 25 8 AM; truck payment Sep 24 noon."""
    l2 = load("L2", 1200).model_copy(update={"origin": RDU})
    chain, loads = chain_of((load("L1", 1200), "2026-09-22T08:00:00", "2026-09-23T10:00:00"),
                            (l2, "2026-09-24T08:00:00", "2026-09-25T06:00:00"))
    chain.schedule[1]["depart_at"] = "2026-09-23T10:00:00"
    mid_trip = [{"payee": "Truck payment", "amount": 2150.0, "due_date": date(2026, 9, 24)}]
    return chain, loads, mid_trip


def test_route_is_continuous_and_matches_the_chart():
    chain, loads, bills = two_load_trip()
    route, stops = balance_along_route(chain, loads, RIC, RIC, 2700.0, bills, TODAY)
    cf = simulate(chain, loads, 2700.0, bills, TODAY)
    # stretches join up end to start, from his start to home
    assert route[0]["from"] == [RIC.lat, RIC.lng] and route[-1]["to"] == [RIC.lat, RIC.lng]
    for a, b in zip(route, route[1:]):
        assert a["end"] == b["start"] and a["to"] == pytest.approx(b["from"])
    # same events, same totals, same low point as the chart
    assert [s["label"] for s in stops] == [e["label"] for e in cf.timeline[1:]]
    assert stops[-1]["balance"] == cf.timeline[-1]["balance"]
    assert min(r["balance"] for r in route) == pytest.approx(cf.lowest_balance)


def test_red_starts_where_the_truck_payment_posts_mid_load():
    chain, loads, bills = two_load_trip()
    route, stops = balance_along_route(chain, loads, RIC, RIC, 2700.0, bills, TODAY)
    first_red = next(r for r in route if r["balance"] < 0)
    assert first_red["start"] == "2026-09-24T12:00:00" and first_red["loaded"] is True
    bill = next(s for s in stops if s["kind"] == "bill")
    assert bill["at"] == "2026-09-24T12:00:00"
    # 4 of 22 hours into RDU -> CLT: between the two cities, not at either end
    assert CLT.lat < bill["lat"] < RDU.lat and CLT.lng < bill["lng"] < RDU.lng
    assert [bill["lat"], bill["lng"]] == pytest.approx(first_red["from"], abs=1e-4)


def test_advance_removes_the_red_and_shows_up_at_delivery():
    chain, loads, bills = two_load_trip()
    route, stops = balance_along_route(chain, loads, RIC, RIC, 2700.0, bills, TODAY, advance={"L1"})
    assert all(r["balance"] >= 0 for r in route)
    adv = next(s for s in stops if s["kind"] == "advance")
    assert adv["at"] == "2026-09-23T10:00:00" and [adv["lat"], adv["lng"]] == pytest.approx([CLT.lat, CLT.lng])


def test_route_needs_coordinates():
    chain, loads, bills = two_load_trip()
    assert balance_along_route(chain, loads, Place(city="Nowhere"), RIC, 2700.0, bills, TODAY) == ([], [])


# ---- Feature B: advances already taken ----
def test_taken_advance_is_in_the_timeline_and_clears_the_shortfall():
    chain, loads, bills = two_load_trip()
    before = simulate(chain, loads, 2700.0, bills, TODAY)
    assert before.advance_load_ids == ["L1"]
    after = simulate(chain, loads, 2700.0, bills, TODAY, advance={"L1"})
    assert after.shortfall is False and after.advance_load_ids == [] and after.quick_pay_cost == 0
    assert "Capital One advance on L1" in [e["label"] for e in after.timeline]
    assert {e["label"] for e in after.later} == {"Advance on L1 repaid", "Pay for L1 (Blue Ridge Logistics)",
                                                 "Pay for L2 (Blue Ridge Logistics)"}


def test_advance_on_a_load_not_on_this_run_is_ignored():
    chain, loads, bills = two_load_trip()
    cf = simulate(chain, loads, 2700.0, bills, TODAY, advance={"OTHER"})
    assert cf.shortfall is True and cf.advance_load_ids == ["L1"]
