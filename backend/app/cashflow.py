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

from app.models import CashflowCheck, Chain, Load, Place

STATUS = "live"

Event = tuple[datetime, str, float, str]           # (when, label, amount, kind: fuel | bill | pay | advance)
BILL_HOUR = 12                                      # bills post at noon on their due date


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(str(value))


def _as_date(value) -> date:
    return value if isinstance(value, date) and not isinstance(value, datetime) else _as_datetime(value).date()


def _noon(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, BILL_HOUR)


def home_date(chain: Chain, today: date) -> date:
    """The day he's back home: first departure + chain.days (days include rests and the home deadhead)."""
    if not chain.schedule:
        return today
    return (_as_datetime(chain.schedule[0]["depart_at"]) + timedelta(days=chain.days)).date()


def _sorted(events: list[Event]) -> list[Event]:
    # by day, money out before money in on the same day (worst case for the driver), then by time
    return sorted(events, key=lambda e: (e[0].date(), e[2] >= 0, e[0]))


def _events(chain: Chain, loads_by_id: dict[str, Load], bills: list[dict], today: date,
            advance: set[str]) -> tuple[list[Event], list[Event]]:
    """(events inside the trip window, events after he's home). Only the first list moves the balance."""
    home = home_date(chain, today)
    events: list[Event] = []
    later: list[Event] = []
    for leg, stop in zip(chain.legs, chain.schedule):
        load = loads_by_id[leg.load_id]
        events.append((_as_datetime(stop["pickup_at"]), f"Diesel for {leg.load_id}", -leg.fuel_cost, "fuel"))
        delivered = _as_datetime(stop["delivered_at"])
        take_home = load.rate_usd - leg.dispatch_fee
        who = f" ({load.broker})" if load.broker else ""
        paid_on = _noon(delivered.date() + timedelta(days=load.payment_terms_days))
        pay = (paid_on, f"Pay for {leg.load_id}{who}", take_home, "pay")
        if leg.load_id in advance:
            fee = load.rate_usd * load.quick_pay_fee_pct
            events.append((delivered, f"Capital One advance on {leg.load_id}", take_home - fee, "advance"))
            later += [pay, (paid_on, f"Advance on {leg.load_id} repaid", -take_home, "bill")]
        else:
            (events if paid_on.date() <= home else later).append(pay)
    for bill in bills:
        due = _as_date(bill["due_date"])
        if today <= due <= home:                          # only bills due while he's on this trip
            events.append((_noon(due), str(bill["payee"]), -float(bill["amount"]), "bill"))
    return _sorted(events), _sorted(later)


def _run(start_balance: float, today: date, events: list[Event]):
    balance = start_balance
    lowest, lowest_date = start_balance, today
    timeline = [{"date": today.isoformat(), "label": "Checking balance today", "amount": 0.0,
                 "balance": round(start_balance, 2)}]
    for when, label, amount, _ in events:
        balance += amount
        timeline.append({"date": when.date().isoformat(), "label": label, "amount": round(amount, 2),
                         "balance": round(balance, 2)})
        if balance < lowest:
            lowest, lowest_date = balance, when.date()
    return lowest, lowest_date, timeline


def _stretches(chain: Chain, loads_by_id: dict[str, Load], start: Place, home: Place):
    """The drawn route as timed straight stretches: [(t0, t1, from, to, loaded)]. Start -> pickup -> delivery -> ... -> home."""
    out, here = [], start
    for stop in chain.schedule:
        load = loads_by_id[stop["load_id"]]
        depart, pickup, delivered = (_as_datetime(stop[k]) for k in ("depart_at", "pickup_at", "delivered_at"))
        out.append((depart, pickup, here, load.origin, False))
        out.append((pickup, delivered, load.origin, load.destination, True))
        here = load.destination
    if chain.schedule:
        back = _as_datetime(chain.schedule[0]["depart_at"]) + timedelta(days=chain.days)
        out.append((out[-1][1], max(back, out[-1][1]), here, home, False))
    return out


def _at(stretch, t: datetime) -> tuple[float, float]:
    """Where the truck is at time t on a stretch (straight line, even speed: an estimate, like the miles)."""
    t0, t1, a, b, _ = stretch
    f = 0.0 if t1 <= t0 else min(1.0, max(0.0, (t - t0) / (t1 - t0)))
    return (a.lat + (b.lat - a.lat) * f, a.lng + (b.lng - a.lng) * f)


def balance_along_route(chain: Chain, loads_by_id: dict[str, Load], start: Place, home: Place,
                        start_balance: float, bills: list[dict], today: date,
                        advance: set[str] = frozenset()) -> tuple[list[dict], list[dict]]:
    """(route, money_stops) for the map. Same events as the chart, walked in time order along the route.

    route: stretches cut at every money event, each with the balance while driving it.
    money_stops: one marker per event, placed where the truck is at that moment.
    """
    stretches = _stretches(chain, loads_by_id, start, home)
    if not stretches or any(p.lat is None or p.lng is None for s in stretches for p in (s[2], s[3])):
        return [], []
    t_start, t_end = stretches[0][0], stretches[-1][1]
    events = sorted(_events(chain, loads_by_id, bills, today, set(advance))[0], key=lambda e: e[0])
    clamp = lambda t: min(max(t, t_start), t_end)       # e.g. a bill due today before he leaves

    def where(t: datetime) -> tuple[float, float]:
        return _at(next((s for s in stretches if s[0] <= t <= s[1]), stretches[-1]), t)

    stops, balance = [], start_balance
    for when, label, amount, kind in events:
        balance += amount
        lat, lng = where(clamp(when))
        stops.append({"at": clamp(when).isoformat(), "lat": round(lat, 5), "lng": round(lng, 5), "label": label,
                      "amount": round(amount, 2), "balance": round(balance, 2), "kind": kind})

    route, balance, i = [], start_balance, 0
    for s in stretches:
        t0, t1, _, _, loaded = s
        cuts = [t0] + [clamp(e[0]) for e in events if t0 < clamp(e[0]) < t1] + [t1]
        for a, b in zip(cuts, cuts[1:]):
            while i < len(events) and clamp(events[i][0]) <= a:   # everything paid by the start of this piece
                balance += events[i][2]
                i += 1
            if b > a:
                route.append({"from": list(_at(s, a)), "to": list(_at(s, b)), "start": a.isoformat(),
                              "end": b.isoformat(), "balance": round(balance, 2), "loaded": loaded})
    return route, stops


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
        later=[{"date": w.date().isoformat(), "label": label, "amount": round(amount, 2)} for w, label, amount, _ in later],
    )
