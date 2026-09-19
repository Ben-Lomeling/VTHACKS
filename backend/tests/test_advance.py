"""Feature B: Capital One advance. Nessie writes are faked with MockTransport; never the network."""
import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app import nessie
from app.main import app
from app.models import CashflowCheck, Chain

client = TestClient(app)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEMO_NOW", "2026-09-21T06:00")
    def fail(*_):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(nessie, "_live", fail)
    monkeypatch.setattr(nessie, "_client", fail)
    nessie._CACHE.clear()
    nessie._ADVANCES.clear()
    yield
    nessie._ADVANCES.clear()


def fake_bank(monkeypatch, handler):
    monkeypatch.setattr(nessie, "_client", lambda: httpx.Client(base_url=nessie.BASE, transport=httpx.MockTransport(handler)))


def best_run() -> Chain:
    return Chain.model_validate(client.post("/api/chains", json={"include_board": True}).json()[0])


def test_advance_turns_the_run_green_and_reset_undoes_it():
    chain = best_run()
    before = CashflowCheck.model_validate(client.post("/api/cashflow", json={"chain": chain.model_dump(mode="json")}).json())
    assert before.shortfall and before.advance_load_ids and any(r["balance"] < 0 for r in before.route)
    load_id = before.advance_load_ids[0]
    offer = before.advance_offer
    assert offer["load_id"] == load_id and offer["amount"] == pytest.approx(offer["repay_amount"] - offer["fee"])
    assert offer["on"] < offer["repay_on"]
    r = client.post("/api/advance", json={"chain": chain.model_dump(mode="json"), "load_id": load_id})
    after = CashflowCheck.model_validate(r.json())
    assert after.shortfall is False and all(r["balance"] >= 0 for r in after.route) and after.advance_offer is None
    assert after.advances[0]["amount"] == offer["amount"]
    assert after.advances[0]["load_id"] == load_id and after.advances[0]["source"] == "fixture"
    assert any(m["kind"] == "advance" for m in after.money_stops)
    # tapping twice doesn't book a second advance
    client.post("/api/advance", json={"chain": chain.model_dump(mode="json"), "load_id": load_id})
    assert len(nessie.advances()) == 1
    assert client.post("/api/demo/reset-bank").json() == {"removed": 1}
    again = client.post("/api/cashflow", json={"chain": chain.model_dump(mode="json")}).json()
    assert again["shortfall"] is True and again["advances"] == []


def test_advance_on_a_load_not_on_the_run_is_404():
    chain = best_run()
    r = client.post("/api/advance", json={"chain": chain.model_dump(mode="json"), "load_id": "NOPE"})
    assert r.status_code == 404


def test_create_advance_sends_a_pending_deposit_and_a_readable_repayment_bill(monkeypatch):
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content or b"null")))
        return httpx.Response(201, json={"objectCreated": {"_id": f"id{len(seen)}"}})
    fake_bank(monkeypatch, handler)
    record = nessie.create_advance("L027", 1044, date(2026, 9, 21), 1080, date(2026, 10, 21), " (Blue Ridge Logistics)")
    (m1, p1, deposit), (m2, p2, bill) = seen
    assert (m1, m2) == ("POST", "POST") and p1.endswith("/deposits") and p2.endswith("/bills")
    assert deposit == {"medium": "balance", "transaction_date": "2026-09-21", "status": "pending", "amount": 1044,
                       "description": "CAPITAL ONE ADVANCE L027 (Blue Ridge Logistics)"}
    assert bill["payee"] == nessie.ADVANCE_PAYEE and bill["payment_date"] == "2026-10-21"
    assert bill["recurring_date"] == 21 and bill["payment_amount"] == 1080 and bill["status"] == "pending"
    assert (record["deposit_id"], record["bill_id"], record["source"]) == ("id1", "id2", "live")


def test_failed_bill_rolls_back_the_deposit_and_keeps_the_advance_offline(monkeypatch):
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("/bills"):
            return httpx.Response(500)
        return httpx.Response(201 if request.method == "POST" else 200, json={"objectCreated": {"_id": "dep1"}})
    fake_bank(monkeypatch, handler)
    record = nessie.create_advance("L027", 1044, date(2026, 9, 21), 1080, date(2026, 10, 21))
    assert ("DELETE", "/deposits/dep1") in seen
    assert record["source"] == "fixture" and nessie.advances()["L027"] is record


def test_reset_deletes_only_advance_items(monkeypatch):
    deleted = []
    def handler(request):
        path = request.url.path
        if request.method == "DELETE":
            deleted.append(path)
            return httpx.Response(200)
        if path.endswith("/deposits"):
            return httpx.Response(200, json=[{"_id": "d1", "description": "CAPITAL ONE ADVANCE L027"},
                                             {"_id": "d2", "description": "LOAD PAY Blue Ridge Logistics"}])
        return httpx.Response(200, json=[{"_id": "b1", "payee": nessie.ADVANCE_PAYEE},
                                         {"_id": "b2", "payee": "Truck payment"}])
    fake_bank(monkeypatch, handler)
    assert nessie.reset_advances() == 2
    assert deleted == ["/deposits/d1", "/bills/b1"]


def test_repayment_bill_never_comes_back_as_a_trip_bill(monkeypatch):
    bank = json.loads((nessie.DATA / "nessie_fixture.json").read_text())
    # what Nessie really returns: a pending one-off whose upcoming date is derived from the day of month
    bank["bills"].append({"status": "pending", "payee": nessie.ADVANCE_PAYEE, "payment_date": "2026-10-21",
                          "recurring_date": 21, "upcoming_payment_date": "2026-09-21", "payment_amount": 1080})
    monkeypatch.setattr(nessie, "_live", lambda resources: bank)
    assert all(b["payee"] != nessie.ADVANCE_PAYEE for b in nessie.get_upcoming_bills(45))


def test_live_reads_are_cached(monkeypatch):
    bank = json.loads((nessie.DATA / "nessie_fixture.json").read_text())
    calls = []
    monkeypatch.setattr(nessie, "_live", lambda resources: calls.append(resources) or bank)
    nessie.get_checking_balance(), nessie.get_checking_balance()
    assert calls == [("account",)] and nessie.STATUS == "live"
