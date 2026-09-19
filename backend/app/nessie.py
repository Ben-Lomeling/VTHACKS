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
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, TypeVar

import httpx
from dotenv import dotenv_values

from app.models import TruckProfile

STATUS = "fixture"                 # until a live call succeeds
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend/data"
BASE = "https://api.nessieisreal.com"
LOG = logging.getLogger(__name__)
T = TypeVar("T")
CACHE_SECONDS = 60                 # slow venue Wi-Fi: each live read can take up to 5 s per call
_CACHE: dict[tuple[str, ...], tuple[float, dict]] = {}
ADVANCE_PAYEE = "Capital One advance repayment"
ADVANCE_TAG = "CAPITAL ONE ADVANCE"
_ADVANCES: dict[str, dict] = {}    # load_id -> advance record created by this server (live or offline)
ALIASES = {"Truck Finance Co": "Truck payment", "Commercial Truck Insurance": "Truck insurance", "ELD + Phone": "ELD / phone"}


def _secret(name: str) -> str | None:
    """The local .env file if it has the key, else the environment (that's how Render passes secrets)."""
    return dotenv_values(ROOT / ".env").get(name) or os.getenv(name)


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
    key = _secret("NESSIE_API_KEY")
    if not key:
        raise ValueError("Missing NESSIE_API_KEY (env or root .env)")
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


def _cached_live(resources: tuple[str, ...]) -> dict:
    hit = _CACHE.get(resources)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    snapshot = _live(resources)
    _CACHE[resources] = (time.monotonic(), snapshot)
    return snapshot


def _read(resources: tuple[str, ...], normalize: Callable[[dict], T]) -> tuple[T, str]:
    global STATUS
    try:
        result = normalize(_cached_live(resources))
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
    # Advance repayments are modeled by cashflow itself (and Nessie reports their date wrong: it derives
    # upcoming_payment_date from the day of month), so they never come back in as ordinary bills.
    result, _ = _read(("bills",), lambda data: _expand(
        [b for b in data["bills"] if b.get("payee") != ADVANCE_PAYEE], start, days))
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


# ---- Feature B: Capital One advance (writes) ----
def _client() -> httpx.Client:
    key = _secret("NESSIE_API_KEY")
    if not key:
        raise ValueError("Missing NESSIE_API_KEY (env or root .env)")
    return httpx.Client(base_url=BASE, params={"key": key}, timeout=5)


def _account_path() -> str:
    return f"/accounts/{json.loads((DATA / 'nessie_ids.json').read_text())['account_id']}"


def _post(client: httpx.Client, path: str, body: dict) -> str:
    response = client.post(path, json=body)
    response.raise_for_status()
    return response.json()["objectCreated"]["_id"]


def create_advance(load_id: str, amount: float, on: date, repay_amount: float, repay_on: date,
                   who: str = "") -> dict:
    """Record a Capital One advance in the bank: a deposit on `on` and a repayment bill on `repay_on`.

    Both are `pending` (Nessie doesn't move the balance for them; cashflow adds the advance itself).
    Offline, or if Nessie refuses, the advance is kept in memory with source "fixture" so the demo still works.
    """
    record = {"load_id": load_id, "amount": round(amount, 2), "on": on.isoformat(),
              "repay_amount": round(repay_amount, 2), "repay_on": repay_on.isoformat()}
    deposit_id = None
    try:
        with _client() as client:
            path = _account_path()
            deposit_id = _post(client, path + "/deposits", {
                "medium": "balance", "transaction_date": on.isoformat(), "status": "pending",
                "amount": record["amount"], "description": f"{ADVANCE_TAG} {load_id}{who}"})
            try:
                # recurring_date is required, or Nessie can't read the bill list back (HTTP 400)
                bill_id = _post(client, path + "/bills", {
                    "status": "pending", "payee": ADVANCE_PAYEE, "nickname": f"ADVANCE {load_id}",
                    "payment_date": repay_on.isoformat(), "recurring_date": repay_on.day,
                    "payment_amount": record["repay_amount"]})
            except Exception:
                client.delete(f"/deposits/{deposit_id}")
                raise
        record |= {"deposit_id": deposit_id, "bill_id": bill_id, "source": "live"}
    except Exception as exc:
        LOG.info("Nessie advance write unavailable (%s); keeping it offline", type(exc).__name__)
        offline = f"offline-{uuid.uuid4().hex[:8]}"
        record |= {"deposit_id": offline, "bill_id": offline, "source": "fixture"}
    _CACHE.clear()
    _ADVANCES[load_id] = record
    return record


def advances() -> dict[str, dict]:
    """Advances created since the server started (or the last reset), by load id."""
    return dict(_ADVANCES)


def reset_advances() -> int:
    """Delete every advance deposit and repayment bill on the demo account (for rehearsals). Returns how many."""
    removed = 0
    try:
        with _client() as client:
            path = _account_path()
            for kind, match in (("deposits", lambda d: str(d.get("description", "")).startswith(ADVANCE_TAG)),
                                ("bills", lambda b: b.get("payee") == ADVANCE_PAYEE)):
                response = client.get(f"{path}/{kind}")
                response.raise_for_status()
                for item in filter(match, response.json()):
                    client.delete(f"/{kind}/{item['_id']}").raise_for_status()
                    removed += 1
    except Exception as exc:
        LOG.info("Nessie reset unavailable (%s); clearing offline advances only", type(exc).__name__)
    removed = max(removed, len(_ADVANCES))
    _ADVANCES.clear()
    _CACHE.clear()
    return removed
