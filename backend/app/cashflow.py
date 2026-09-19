"""Cash-flow check: "can I afford this run before it pays?" Pure: no network, no files. Owner: Nischal.

How it works (for judges):
  1. Start from today's checking balance (from Capital One Nessie).
  2. Lay every money event of THIS TRIP on a calendar (today until he's home): diesel is paid on each load's
     pickup day and bills leave on their due dates. Broker pay (rate minus the dispatcher's cut, on delivery
     day + payment terms) usually lands weeks after he's home, so it goes in `later`, not in the balance.
  3. Walk the calendar in order (money out before money in on the same day, to be safe) and track the
     running balance and its lowest point.
  4. If the balance goes below zero, try a Capital One advance (deposited on delivery day, minus a fee, and
     paid back automatically when the broker pays) on the fewest loads needed, earliest delivery first, and
     report whether that fixes it and what it costs.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models import CashflowCheck, Chain, Load

STATUS = "live"

Event = tuple[date, str, float]


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(str(value))


def _as_date(value) -> date:
    return value if isinstance(value, date) and not isinstance(value, datetime) else _as_datetime(value).date()


def home_date(chain: Chain, today: date) -> date:
    """The day he's back home: first departure + chain.days (days include rests and the home deadhead)."""
    if not chain.schedule:
        return today
    return (_as_datetime(chain.schedule[0]["depart_at"]) + timedelta(days=chain.days)).date()


def _sorted(events: list[Event]) -> list[Event]:
    # money out before money in on the same day (worst case for the driver)
    return sorted(events, key=lambda e: (e[0], e[2] >= 0))


def _events(chain: Chain, loads_by_id: dict[str, Load], bills: list[dict], today: date,
            advance: set[str]) -> tuple[list[Event], list[Event]]:
    """(events inside the trip window, events after he's home). Only the first list moves the balance."""
    home = home_date(chain, today)
    events: list[Event] = []
    later: list[Event] = []
    for leg, stop in zip(chain.legs, chain.schedule):
        load = loads_by_id[leg.load_id]
        events.append((_as_date(stop["pickup_at"]), f"Diesel for {leg.load_id}", -leg.fuel_cost))
        delivered = _as_date(stop["delivered_at"])
        take_home = load.rate_usd - leg.dispatch_fee
        who = f" ({load.broker})" if load.broker else ""
        paid_on = delivered + timedelta(days=load.payment_terms_days)
        pay = (paid_on, f"Pay for {leg.load_id}{who}", take_home)
        if leg.load_id in advance:
            fee = load.rate_usd * load.quick_pay_fee_pct
            events.append((delivered, f"Capital One advance on {leg.load_id}", take_home - fee))
            later += [pay, (paid_on, f"Advance on {leg.load_id} repaid", -take_home)]
        else:
            (events if paid_on <= home else later).append(pay)
    for bill in bills:
        due = _as_date(bill["due_date"])
        if today <= due <= home:                          # only bills due while he's on this trip
            events.append((due, str(bill["payee"]), -float(bill["amount"])))
    return _sorted(events), _sorted(later)


def _run(start_balance: float, today: date, events: list[Event]):
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
    events, later = _events(chain, loads_by_id, bills, today, set())
    lowest, lowest_date, timeline = _run(start_balance, today, events)
    shortfall = lowest < 0

    fixes, cost = False, 0.0
    if shortfall:
        by_delivery = sorted(zip(chain.legs, chain.schedule), key=lambda ls: ls[1]["delivered_at"])
        chosen: set[str] = set()
        for leg, _ in by_delivery:                          # add an advance one load at a time
            chosen.add(leg.load_id)
            low, _, _ = _run(start_balance, today, _events(chain, loads_by_id, bills, today, chosen)[0])
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
        later=[{"date": d.isoformat(), "label": label, "amount": round(amount, 2)} for d, label, amount in later],
    )
