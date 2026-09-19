"""Cash-flow check: "can I afford this run before it pays?" Pure: no network, no files. Owner: Nischal.

How it works (for judges):
  1. Start from today's checking balance (from Capital One Nessie).
  2. Lay every money event on a calendar: diesel is paid on each load's pickup day, bills leave on their
     due dates, and each load pays (rate minus the dispatcher's cut) on delivery day + payment terms.
  3. Walk the calendar in order (money out before money in on the same day, to be safe) and track the
     running balance and its lowest point.
  4. If the balance goes below zero, try quick pay (paid 2 days after delivery, minus a fee) on the fewest
     loads needed, earliest delivery first, and report whether that fixes it and what it costs.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models import CashflowCheck, Chain, Load

STATUS = "live"

QUICK_PAY_DAYS = 2


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date() if "T" in str(value) else date.fromisoformat(str(value))


def _events(chain: Chain, loads_by_id: dict[str, Load], bills: list[dict], today: date,
            quick_pay: set[str]) -> list[tuple[date, str, float]]:
    events: list[tuple[date, str, float]] = []
    last_pay = today
    for leg, stop in zip(chain.legs, chain.schedule):
        load = loads_by_id[leg.load_id]
        events.append((_as_date(stop["pickup_at"]), f"Diesel for {leg.load_id}", -leg.fuel_cost))
        delivered = _as_date(stop["delivered_at"])
        take_home = load.rate_usd - leg.dispatch_fee
        who = f" ({load.broker})" if load.broker else ""
        if leg.load_id in quick_pay:
            fee = load.rate_usd * load.quick_pay_fee_pct
            paid_on = delivered + timedelta(days=QUICK_PAY_DAYS)
            events.append((paid_on, f"Quick pay for {leg.load_id}{who}", take_home - fee))
        else:
            paid_on = delivered + timedelta(days=load.payment_terms_days)
            events.append((paid_on, f"Pay for {leg.load_id}{who}", take_home))
        last_pay = max(last_pay, paid_on)
    for bill in bills:
        due = _as_date(bill["due_date"])
        if today <= due <= last_pay:                      # only bills that land before the run finishes paying
            events.append((due, str(bill["payee"]), -float(bill["amount"])))
    # money out before money in on the same day (worst case for the driver)
    events.sort(key=lambda e: (e[0], e[2] >= 0))
    return events


def _run(start_balance: float, today: date, events: list[tuple[date, str, float]]):
    balance = start_balance
    lowest, lowest_date = start_balance, today
    timeline = [{"date": today.isoformat(), "label": "Checking balance today", "amount": 0.0,
                 "balance": round(start_balance, 2)}]
    for d, label, amount in events:
        balance += amount
        timeline.append({"date": d.isoformat(), "label": label, "amount": round(amount, 2),
                         "balance": round(balance, 2)})
        if balance < lowest:
            lowest, lowest_date = balance, d
    return lowest, lowest_date, timeline


def simulate(chain: Chain, loads_by_id: dict[str, Load], start_balance: float, bills: list[dict], today: date) -> CashflowCheck:
    lowest, lowest_date, timeline = _run(start_balance, today, _events(chain, loads_by_id, bills, today, set()))
    shortfall = lowest < 0

    fixes, cost = False, 0.0
    if shortfall:
        by_delivery = sorted(zip(chain.legs, chain.schedule), key=lambda ls: ls[1]["delivered_at"])
        chosen: set[str] = set()
        for leg, _ in by_delivery:                          # add quick pay one load at a time
            chosen.add(leg.load_id)
            low, _, _ = _run(start_balance, today, _events(chain, loads_by_id, bills, today, chosen))
            cost = sum(loads_by_id[i].rate_usd * loads_by_id[i].quick_pay_fee_pct for i in chosen)
            if low >= 0:
                fixes = True
                break

    return CashflowCheck(
        starting_balance=start_balance,
        lowest_balance=round(lowest, 2),
        lowest_balance_date=lowest_date,
        shortfall=shortfall,
        quick_pay_fixes_it=fixes,
        quick_pay_cost=round(cost, 2),
        timeline=timeline,
    )
