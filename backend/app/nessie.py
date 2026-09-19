"""Capital One Nessie client + costs-from-bank.

Owner: NESSIE teammate. STUB (Phase 0) — replace the internals, keep the signatures (SPEC.md
"Module interfaces"). Nothing outside this file should ever see raw Nessie JSON.
"""
from datetime import date, timedelta

from app.models import TruckProfile

STATUS = "stub"

_RECURRING = [("Truck payment", 2150.0, 1), ("Truck insurance", 1100.0, 5), ("ELD / phone", 65.0, 15)]


def data_source() -> str:
    return "stub"


def get_checking_balance() -> float:
    return 3800.0


def get_upcoming_bills(days: int = 45) -> list[dict]:
    start = date.today()
    out = []
    for i in range(days + 1):
        d = start + timedelta(days=i)
        for payee, amount, dom in _RECURRING:
            if d.day == dom:
                out.append({"payee": payee, "amount": amount, "due_date": d})
    return out


def get_costs_from_bank(profile: TruckProfile) -> dict:
    proposed = profile.model_copy(update={
        "fuel_price": 3.92, "variable_cpm": 0.27, "fixed_monthly": 3315.0, "cost_source": "nessie",
    })
    return {
        "current": profile,
        "proposed": proposed,
        "evidence": {
            "fuel_gallons": 4210.5, "fuel_spend": 16505.16, "maintenance_spend": 8100.0,
            "bills": [{"payee": p, "amount": a, "day_of_month": d} for p, a, d in _RECURRING],
            "unparsed_count": 0, "window_days": 90, "source": "stub",
        },
    }
