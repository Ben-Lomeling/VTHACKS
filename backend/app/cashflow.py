"""Cash-flow simulation — pure. Owner: Nischal.

STUB (Phase 0): returns a fixed timeline that dips negative on the 1st. Real simulation lands in Phase 3.
"""
from datetime import date

from app.models import CashflowCheck, Chain, Load

STATUS = "stub"


def simulate(chain: Chain, loads_by_id: dict[str, Load], start_balance: float, bills: list[dict], today: date) -> CashflowCheck:
    events = [
        ("2026-09-22", "Fuel for first load", -343.0),
        ("2026-10-01", "Truck payment", -2150.0),
        ("2026-10-05", "Insurance", -1100.0),
        ("2026-10-15", "ELD / phone", -65.0),
        ("2026-10-22", "Pay for first load", 1080.0),
    ]
    balance, timeline = start_balance, []
    for d, label, amount in events:
        balance += amount
        timeline.append({"date": d, "label": label, "amount": amount, "balance": round(balance, 2)})
    low = min(timeline, key=lambda e: e["balance"])
    return CashflowCheck(
        starting_balance=start_balance, lowest_balance=low["balance"],
        lowest_balance_date=date.fromisoformat(low["date"]), shortfall=low["balance"] < 0,
        quick_pay_fixes_it=True, quick_pay_cost=36.0, timeline=timeline,
    )
