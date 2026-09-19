"""Nessie sandbox access with an atomic per-operation offline fallback.

Only this module exposes normalized bank data to the application. Secrets are
read from root .env; errors log their type, never a credential-bearing URL.
"""
from __future__ import annotations

import calendar
import json
import logging
import math
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, TypeVar

import httpx
from dotenv import dotenv_values

from app.models import TruckProfile

STATUS = "live"
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend/data"
BASE = "https://api.nessieisreal.com"
LOG = logging.getLogger(__name__)
T = TypeVar("T")
ALIASES = {"Truck Finance Co": "Truck payment", "Commercial Truck Insurance": "Truck insurance", "ELD + Phone": "ELD / phone"}


def _today() -> date:
    config = dotenv_values(ROOT / ".env")
    raw = os.getenv("DEMO_NOW", config.get("DEMO_NOW", "2026-09-21T06:00"))
    return datetime.fromisoformat(raw).date() if raw else date.today()


def _number(value: object) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite bank amount")
    return result


def _live(resources: tuple[str, ...]) -> dict:
    key = dotenv_values(ROOT / ".env").get("NESSIE_API_KEY")
    if not key:
        raise ValueError("Missing root .env Nessie key")
    ids = json.loads((DATA / "nessie_ids.json").read_text())
    with httpx.Client(base_url=BASE, params={"key": key}, timeout=5) as client:
        def get(path: str) -> dict | list:
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        snapshot = {}
        account = f"/accounts/{ids['account_id']}"
        for resource in resources:
            if resource != "merchants":
                snapshot[resource] = get(account if resource == "account" else account + "/" + resource)
        if "merchants" in resources:
            merchant_ids = {p["merchant_id"] for p in snapshot["purchases"]}
            snapshot["merchants"] = [get(f"/merchants/{mid}") for mid in sorted(merchant_ids)]
        return snapshot


def _read(resources: tuple[str, ...], normalize: Callable[[dict], T]) -> tuple[T, str]:
    global STATUS
    try:
        result = normalize(_live(resources))
        source = "live"
    except Exception as exc:
        LOG.info("Nessie live unavailable (%s); using fixture", type(exc).__name__)
        STATUS = "fixture"
        result = normalize(json.loads((DATA / "nessie_fixture.json").read_text()))
        source = "fixture"
    STATUS = source
    LOG.info("Nessie source=%s", source)
    return result, source


def data_source() -> str:
    _, source = _read(("account",), lambda data: _number(data["account"]["balance"]))
    return source


def get_checking_balance() -> float:
    result, _ = _read(("account",), lambda data: _number(data["account"]["balance"]))
    return result


def _bill(bill: dict) -> dict:
    payee = bill["payee"]
    return {"payee": ALIASES.get(payee, payee), "amount": _number(bill["payment_amount"]),
            "day_of_month": int(bill.get("recurring_date") or 0)}


def _expand(bills: list[dict], start: date, days: int) -> list[dict]:
    end = start + timedelta(days=days)
    out = []
    for raw in bills:
        if raw.get("status") in {"cancelled", "completed"}:
            continue
        bill = _bill(raw)
        first_raw = raw.get("upcoming_payment_date") or raw.get("payment_date")
        first = date.fromisoformat(first_raw) if first_raw else start
        recurring = raw.get("status") == "recurring"
        dom = bill["day_of_month"]
        if recurring and not 1 <= dom <= 31:
            raise ValueError("Invalid recurring day")
        month = start.replace(day=1)
        while month <= end:
            due = month.replace(day=min(dom, calendar.monthrange(month.year, month.month)[1])) if recurring else first
            if start <= due <= end and due >= first:
                out.append({"payee": bill["payee"], "amount": bill["amount"], "due_date": due})
            if not recurring:
                break
            month = (month + timedelta(days=32)).replace(day=1)
    return sorted(out, key=lambda b: (b["due_date"], b["payee"]))


def get_upcoming_bills(days: int = 45) -> list[dict]:
    start = _today()
    result, _ = _read(("bills",), lambda data: _expand(data["bills"], start, days))
    return result


def _gallons(description: object) -> float | None:
    if not isinstance(description, str):
        return None
    match = re.search(r"\bDIESEL\s+(\d+(?:\.\d+)?)\s+GAL\b", description, re.IGNORECASE)
    if not match:
        return None
    value = float(match[1])
    return value if math.isfinite(value) and value > 0 else None


def _costs(data: dict, profile: TruckProfile, today: date) -> dict:
    merchants = {m["_id"]: m for m in data["merchants"]}
    gallons = fuel = maintenance = 0.0
    unparsed = 0
    for purchase in data["purchases"]:
        if purchase.get("status") != "completed":
            continue
        day = date.fromisoformat(purchase["purchase_date"])
        if not today - timedelta(days=90) <= day < today:
            continue
        category = merchants[purchase["merchant_id"]]["category"]
        categories = {category.lower()} if isinstance(category, str) else {c.lower() for c in category}
        amount = _number(purchase["amount"])
        if "fuel" in categories:
            parsed = _gallons(purchase.get("description"))
            if parsed is None:
                unparsed += 1
                continue
            gallons += parsed
            fuel += amount
        elif categories & {"tires", "repair", "repairs", "maintenance", "tolls"}:
            maintenance += amount
    bills = [_bill(b) for b in data["bills"] if b.get("status") == "recurring"]
    miles = profile.miles_per_month * 3
    if not math.isfinite(miles) or miles <= 0:
        raise ValueError("Positive miles_per_month required for bank cost estimate")
    proposed = profile.model_copy(update={"fuel_price": fuel / gallons if gallons else profile.fuel_price,
        "variable_cpm": maintenance / miles, "fixed_monthly": sum(b["amount"] for b in bills), "cost_source": "nessie"})
    return {"current": profile, "proposed": proposed, "evidence": {"fuel_gallons": gallons,
        "fuel_spend": fuel, "maintenance_spend": maintenance, "bills": bills,
        "unparsed_count": unparsed, "window_days": 90}}


def get_costs_from_bank(profile: TruckProfile) -> dict:
    today = _today()
    result, source = _read(("purchases", "merchants", "bills"), lambda data: _costs(data, profile, today))
    result["evidence"]["source"] = source
    return result
