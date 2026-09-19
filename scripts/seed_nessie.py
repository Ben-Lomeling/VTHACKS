"""Seed once: run with backend/.venv/bin/python scripts/seed_nessie.py.

Credentials come from the repository root .env. A checkpoint is reserved before
any writes; an interrupted seed must be inspected, never blindly rerun.
Request fields follow nessieisreal's official Python and JavaScript SDKs.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend/data/nessie_ids.json"
BASE = "https://api.nessieisreal.com"
BILLS = [("Truck payment", 2150, 1), ("Truck insurance", 1100, 5), ("ELD / phone", 65, 15)]
MERCHANTS = [
    ("Pilot Travel Center Wytheville", "fuel", "Wytheville", "VA", 36.948, -81.085),
    ("Love's Travel Stop Raphine", "fuel", "Raphine", "VA", 37.936, -79.232),
    ("TA Truck Service Greensboro", "fuel", "Greensboro", "NC", 36.073, -79.792),
    ("Blue Ridge Truck Tires", "tires", "Salem", "VA", 37.293, -80.055),
    ("Valley Diesel Repair", "repair", "Roanoke", "VA", 37.271, -79.941),
    ("E-ZPass Virginia", "tolls", "Richmond", "VA", 37.541, -77.436),
]


def history(today: date) -> tuple[list[dict], list[dict]]:
    # These targets are placeholders until the driver's real numbers arrive:
    # $3.92/gal, $8,100 / 30,000 miles = $0.27/mi, $3,315/month.
    purchases = []
    for i in range(45):
        gallons = Decimal("93.5") if i < 44 else Decimal("96.5")
        purchases.append({"merchant_index": i % 3, "medium": "balance",
            "purchase_date": (today - timedelta(days=90 - i * 2)).isoformat(),
            "amount": (366 + i % 2) if i < 44 else 379, "status": "completed",
            "description": f"DIESEL {gallons} GAL @ 3.920"})
    for i in range(10):
        purchases.append({"merchant_index": 5, "medium": "balance",
            "purchase_date": (today - timedelta(days=90 - i * 9)).isoformat(),
            "amount": 110.0, "status": "completed", "description": "TOLLS"})
    for days, merchant, amount, description in [(70, 3, 3000, "DRIVE TIRES"),
            (41, 4, 3000, "BRAKE JOB"), (12, 4, 1000, "PM SERVICE")]:
        purchases.append({"merchant_index": merchant, "medium": "balance",
            "purchase_date": (today - timedelta(days=days)).isoformat(),
            "amount": amount, "status": "completed", "description": description})
    brokers = ["Blue Ridge Logistics", "Atlantic Freight Brokers", "Piedmont Transport Group"]
    deposits = [{"medium": "balance", "transaction_date": (today - timedelta(days=d)).isoformat(),
        "status": "completed", "amount": 1200, "description": f"LOAD PAY {brokers[i % 3]}"}
        for i, d in enumerate(range(88, 0, -6))]
    return purchases, deposits


def request(client: httpx.Client, method: str, path: str, body: dict | None = None) -> dict | list:
    try:
        response = client.request(method, path, json=body) if body is not None else client.request(method, path)
    except httpx.HTTPError as exc:
        # Exception strings include credential-bearing URLs; never print them.
        raise RuntimeError(f"{method} {path}: {type(exc).__name__}") from None
    if not response.is_success:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}")
    return response.json()


def seed(client: httpx.Client, today: date, out: Path = OUT, *, resume: bool = False) -> dict:
    purchases, deposits = history(today)
    # Verified against the live API: completed transactions do not mutate
    # account.balance here, and purchase amounts are integers (fractional dollars
    # are truncated). Use whole dollars; always assert the final GET below.
    opening = Decimal("3800")
    ids = {"state": "in_progress", "merchants": {}, "purchases": [], "deposits": [], "bills": []}
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents duplicate customers even after partial failure.
    if resume:
        ids = json.loads(out.read_text())
    else:
        with out.open("x") as file:
            json.dump(ids, file, indent=2)

    def post(path: str, body: dict) -> dict:
        return request(client, "POST", path, body)["objectCreated"]

    def checkpoint() -> None:
        temp = out.with_suffix(".tmp")
        temp.write_text(json.dumps(ids, indent=2) + "\n")
        temp.replace(out)

    address = {"street_number": "100", "street_name": "Main St", "city": "Roanoke", "state": "VA", "zip": "24011"}
    customer = {"_id": ids["customer_id"]} if "customer_id" in ids else post("/customers", {"first_name": "Dad's", "last_name": "LLC", "address": address})
    ids["customer_id"] = customer["_id"]
    checkpoint()
    account = {"_id": ids["account_id"]} if "account_id" in ids else post(f"/customers/{customer['_id']}/accounts", {"type": "Checking", "nickname": "Truck Operating", "rewards": 0, "balance": float(opening)})
    ids["account_id"] = account["_id"]
    checkpoint()
    path = f"/accounts/{account['_id']}"
    for name, category, city, state, lat, lng in MERCHANTS:
        if name in ids["merchants"]:
            continue
        # Live API currently requires a string, unlike the historical JS SDK.
        merchant = post("/merchants", {"name": name, "category": category,
            "address": {**address, "city": city, "state": state}, "geocode": {"lat": lat, "lng": lng}})
        ids["merchants"][name] = {"id": merchant["_id"], "category": category}
        checkpoint()
    # Deposits first keep sufficient funds for every completed purchase.
    for body in deposits[len(ids["deposits"]):]:
        ids["deposits"].append(post(path + "/deposits", body)["_id"])
        checkpoint()
    for purchase in purchases[len(ids["purchases"]):]:
        body = dict(purchase)
        merchant = MERCHANTS[body.pop("merchant_index")][0]
        body["merchant_id"] = ids["merchants"][merchant]["id"]
        ids["purchases"].append(post(path + "/purchases", body)["_id"])
        checkpoint()
    for payee, amount, dom in BILLS[len(ids["bills"]):]:
        nxt = today.replace(day=dom)
        if nxt < today:
            nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=dom)
        ids["bills"].append(post(path + "/bills", {"status": "recurring", "payee": payee,
            "nickname": payee, "payment_date": nxt.isoformat(), "recurring_date": dom,
            "payment_amount": amount})["_id"])
        checkpoint()
    account = request(client, "GET", path)
    bills = request(client, "GET", path + "/bills")
    if abs(Decimal(str(account["balance"])) - Decimal("3800")) > 1:
        raise RuntimeError("Final balance is not $3,800; inspect the checkpoint and account before proceeding.")
    if sorted((b["payee"], b["payment_amount"], b["recurring_date"]) for b in bills) != sorted(BILLS):
        raise RuntimeError("Final bills do not match the demo contract.")
    ids["state"] = "complete"
    checkpoint()
    return {"account": account, "bills": bills}


def main() -> None:
    if OUT.exists():
        raise SystemExit("nessie_ids.json already exists; refusing to create a second customer. Inspect it before proceeding.")
    config = dotenv_values(ROOT / ".env")
    key = config.get("NESSIE_API_KEY")
    if not key:
        raise SystemExit("Set NESSIE_API_KEY in the repository root .env.")
    import os
    raw = os.getenv("DEMO_NOW", config.get("DEMO_NOW", "2026-09-21T06:00"))
    today = datetime.fromisoformat(raw).date() if raw else date.today()
    try:
        with httpx.Client(base_url=BASE, params={"key": key}, timeout=5) as client:
            result = seed(client, today)
    except Exception as exc:
        raise SystemExit(f"Seed stopped ({type(exc).__name__}). Inspect nessie_ids.json; do not retry blindly. " + (str(exc) if isinstance(exc, RuntimeError) else "")) from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
