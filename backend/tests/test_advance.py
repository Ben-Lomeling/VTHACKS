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


# ---- Reliability: the public site never writes to the bank ----
def test_writes_off_keeps_the_advance_in_memory(monkeypatch):
    calls = []
    monkeypatch.setattr(nessie, "_client", lambda: calls.append("client") or (_ for _ in ()).throw(AssertionError))
    monkeypatch.setenv("NESSIE_WRITES", "off")
    monkeypatch.setattr(nessie, "dotenv_values", lambda path: {})
    assert nessie.writes_enabled() is False
    record = nessie.create_advance("L027", 1044, date(2026, 9, 21), 1080, date(2026, 10, 21))
    assert record["source"] == "fixture" and calls == []          # no bank call at all
    assert nessie.reset_advances() == 1 and calls == []
    assert client.get("/api/health").json()["bank_writes"] == "off"


def test_writes_on_by_default(monkeypatch):
    monkeypatch.delenv("NESSIE_WRITES", raising=False)
    monkeypatch.setattr(nessie, "dotenv_values", lambda path: {})
    assert nessie.writes_enabled() is True
    assert client.get("/api/health").json()["bank_writes"] == "on"


def test_restart_reloads_advances_from_the_bank(monkeypatch):
    """Render restarts mid-demo; the advance already in the bank must come back."""
    def handler(request):
        if request.url.path.endswith("/deposits"):
            return httpx.Response(200, json=[
                {"_id": "dep1", "description": "CAPITAL ONE ADVANCE L027 (Blue Ridge Logistics)",
                 "amount": 1044, "transaction_date": "2026-09-21"},
                {"_id": "dep2", "description": "LOAD PAY Blue Ridge Logistics", "amount": 1200,
                 "transaction_date": "2026-09-01"}])
        return httpx.Response(200, json=[
            {"_id": "bill1", "payee": nessie.ADVANCE_PAYEE, "nickname": "ADVANCE L027",
             "payment_amount": 1080, "payment_date": "2026-10-21"},
            {"_id": "bill2", "payee": "Truck payment", "payment_amount": 2150, "payment_date": "2026-09-22"}])
    fake_bank(monkeypatch, handler)
    assert nessie.load_existing_advances() == 1
    advance = nessie.advances()["L027"]
    assert advance["deposit_id"] == "dep1" and advance["bill_id"] == "bill1"
    assert advance["amount"] == 1044 and advance["repay_on"] == "2026-10-21"


def test_reload_is_skipped_when_writes_are_off(monkeypatch):
    monkeypatch.setenv("NESSIE_WRITES", "off")
    monkeypatch.setattr(nessie, "dotenv_values", lambda path: {})
    monkeypatch.setattr(nessie, "_client", lambda: (_ for _ in ()).throw(AssertionError("no bank call")))
    assert nessie.load_existing_advances() == 0
