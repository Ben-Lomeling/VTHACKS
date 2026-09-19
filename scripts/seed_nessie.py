"""Seed Capital One Nessie with a demo owner-operator's bank history.

UNTESTED DRAFT: written without network access to Nessie. Before trusting it, open the Nessie docs
(http://api.nessieisreal.com/documentation) and confirm the request bodies below. Run it once,
look at the responses, fix field names if Nessie rejects anything, and then save the result
as backend/data/nessie_fixture.json so the demo still works if Nessie is down.

Usage:  NESSIE_API_KEY=... python scripts/seed_nessie.py
"""
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE = "http://api.nessieisreal.com"
KEY = os.environ["NESSIE_API_KEY"]
OUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "nessie_ids.json"
random.seed(7)
client = httpx.Client(base_url=BASE, params={"key": KEY}, timeout=20)


def post(path: str, body: dict) -> dict:
    r = client.post(path, json=body)
    if r.status_code >= 300:
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text}")
    data = r.json()
    return data.get("objectCreated", data)


def addr(num, street, city, state, zip_):
    return {"street_number": num, "street_name": street, "city": city, "state": state, "zip": zip_}


ids: dict = {"merchants": {}}

customer = post("/customers", {"first_name": "Demo", "last_name": "Trucking LLC",
                               "address": addr("100", "Main St", "Roanoke", "VA", "24011")})
ids["customer_id"] = customer["_id"]

account = post(f"/customers/{customer['_id']}/accounts",
               {"type": "Checking", "nickname": "Truck Operating", "rewards": 0, "balance": 3800})
ids["account_id"] = account["_id"]
acct = account["_id"]

# name -> (category, city, state, lat, lng)
MERCHANTS = {
    "Pilot Travel Center Wytheville": ("fuel", "Wytheville", "VA", 36.948, -81.085),
    "Love's Travel Stop Raphine": ("fuel", "Raphine", "VA", 37.936, -79.232),
    "TA Truck Service Greensboro": ("fuel", "Greensboro", "NC", 36.073, -79.792),
    "Blue Ridge Truck Tires": ("tires", "Salem", "VA", 37.293, -80.055),
    "Valley Diesel Repair": ("repair", "Roanoke", "VA", 37.271, -79.941),
    "E-ZPass Virginia": ("tolls", "Richmond", "VA", 37.541, -77.436),
}
for name, (cat, city, st, lat, lng) in MERCHANTS.items():
    m = post("/merchants", {"name": name, "category": cat,
                            "address": addr("1", "Truck Plaza Dr", city, st, "24000"),
                            "geocode": {"lat": lat, "lng": lng}})
    ids["merchants"][name] = {"id": m["_id"], "category": cat}

today = date.today()
fuel_names = [n for n, v in MERCHANTS.items() if v[0] == "fuel"]

# ~90 days of spending. Gallons are written into the description so nessie.py can derive $/gal.
for d in range(90, 0, -1):
    day = (today - timedelta(days=d)).isoformat()
    if d % 2 == 0:  # fuel every other day
        gal = round(random.uniform(90, 140), 1)
        price = round(random.uniform(3.65, 3.95), 3)
        name = random.choice(fuel_names)
        post(f"/accounts/{acct}/purchases", {
            "merchant_id": ids["merchants"][name]["id"], "medium": "balance", "purchase_date": day,
            "amount": round(gal * price, 2), "status": "completed",
            "description": f"DIESEL {gal} GAL @ {price}"})
    if d % 9 == 0:
        post(f"/accounts/{acct}/purchases", {
            "merchant_id": ids["merchants"]["E-ZPass Virginia"]["id"], "medium": "balance",
            "purchase_date": day, "amount": round(random.uniform(40, 120), 2),
            "status": "completed", "description": "TOLLS"})
for d, merchant, amt, desc in [(70, "Blue Ridge Truck Tires", 2400.00, "2 DRIVE TIRES"),
                               (41, "Valley Diesel Repair", 1850.00, "BRAKE JOB"),
                               (12, "Valley Diesel Repair", 640.00, "PM SERVICE")]:
    post(f"/accounts/{acct}/purchases", {
        "merchant_id": ids["merchants"][merchant]["id"], "medium": "balance",
        "purchase_date": (today - timedelta(days=d)).isoformat(), "amount": amt,
        "status": "completed", "description": desc})

# Recurring bills: these drive the cash-flow check.
for payee, amt, dom in [("Truck Finance Co", 2150.00, 1), ("Commercial Truck Insurance", 1100.00, 5),
                        ("ELD + Phone", 65.00, 15)]:
    nxt = today.replace(day=dom)
    if nxt <= today:
        nxt = (nxt.replace(day=1) + timedelta(days=32)).replace(day=dom)
    post(f"/accounts/{acct}/bills", {
        "status": "recurring", "payee": payee, "nickname": payee,
        "payment_date": nxt.isoformat(), "recurring_date": dom, "payment_amount": amt})

# Past load payments.
brokers = ["Blue Ridge Logistics", "Atlantic Freight Brokers", "Piedmont Transport Group"]
for d in range(88, 0, -6):
    post(f"/accounts/{acct}/deposits", {
        "medium": "balance", "transaction_date": (today - timedelta(days=d)).isoformat(),
        "status": "completed", "amount": round(random.uniform(1100, 2600), 2),
        "description": f"LOAD PAY {random.choice(brokers)}"})

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(ids, indent=2))
print(f"Seeded. IDs written to {OUT}")
