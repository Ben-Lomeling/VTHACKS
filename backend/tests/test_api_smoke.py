"""Every route in SPEC.md's API table returns valid JSON of the right shape. No network."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CashflowCheck, Chain, ExtractionResult, Load, LoadEconomics, TruckProfile

client = TestClient(app)


def test_profile_get_put():
    p = client.get("/api/profile").json()
    TruckProfile.model_validate(p)
    r = client.put("/api/profile", json=p)
    assert r.status_code == 200


def test_board_is_simulated():
    loads = [Load.model_validate(x) for x in client.get("/api/board").json()]
    assert len(loads) == 60 and all(l.source == "simulated" for l in loads)


def test_extract_text_and_image():
    r = client.post("/api/extract", data={"text": "RICH VA -> CLT NC 2400 all in"})
    assert r.status_code == 200
    ExtractionResult.model_validate(r.json())
    r = client.post("/api/extract", files={"image": ("offer.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200


def test_extract_places_cities_on_the_map():
    load = client.post("/api/extract", data={"text": "Greensboro, NC -> Jacksonville, FL $1,200"}).json()["load"]
    assert load["origin"]["lat"] is not None and load["destination"]["lng"] is not None


def test_extract_requires_input():
    assert client.post("/api/extract", data={}).status_code == 400


def _pasted_load() -> dict:
    return client.post("/api/extract", data={"text": "x"}).json()["load"]


def test_evaluate_offers_chains_cashflow_explain_counter():
    load = _pasted_load()
    econ = client.post("/api/evaluate", json={"load": load}).json()
    LoadEconomics.model_validate(econ)

    ranked = client.post("/api/offers", json={"loads": [load]}).json()
    assert len(ranked) == 1

    chains = client.post("/api/chains", json={"seed_load_ids": [load["id"]], "include_board": True}).json()
    assert chains, "expected at least one chain"
    chain = Chain.model_validate(chains[0])

    cf = client.post("/api/cashflow", json={"chain": chain.model_dump(mode="json")}).json()
    CashflowCheck.model_validate(cf)

    text = client.post("/api/explain", json={"economics": econ, "chain": chains[0], "cashflow": cf}).json()
    assert isinstance(text["text"], str) and text["text"]

    msg = client.post("/api/counter-message", json={"economics": econ}).json()
    assert "$" in msg["text"]


def test_chains_unknown_seed_id_is_404():
    r = client.post("/api/chains", json={"seed_load_ids": ["NOPE"], "include_board": True})
    assert r.status_code == 404


def test_costs_from_bank_shape():
    body = client.get("/api/costs/from-bank").json()
    assert set(body) == {"current", "proposed", "evidence"}
    TruckProfile.model_validate(body["proposed"])


def test_health_lists_every_module():
    mods = client.get("/api/health").json()["modules"]
    assert set(mods) == {"profit", "geo", "optimizer", "cashflow", "gemini", "nessie"}


def test_evaluate_computes_missing_loaded_miles_from_geo():
    """No loaded_miles_est -> main.py resolves both cities and uses geo distance."""
    load = {"id": "PX1", "origin": {"city": "Richmond, VA"}, "destination": {"city": "Charlotte, NC"},
            "rate_usd": 1200, "source": "pasted"}
    econ = client.post("/api/evaluate", json={"load": load}).json()
    assert 290 < econ["loaded_miles"] < 305        # ~248 mi straight x 1.2 ~= 297
    assert econ["posted_rpm"] == pytest.approx(1200 / econ["loaded_miles"])


def test_evaluate_bad_rate_is_422_with_message():
    load = {"id": "PX2", "origin": {"city": "Richmond, VA"}, "destination": {"city": "Charlotte, NC"},
            "rate_usd": 0, "loaded_miles_est": 300, "source": "pasted"}
    r = client.post("/api/evaluate", json={"load": load})
    assert r.status_code == 422 and "rate_usd must be > 0" in r.json()["detail"]


def test_profile_accepts_any_cached_city_without_coords():
    p = client.get("/api/profile").json()
    p["home"] = {"city": "Atlanta, GA"}
    p["current_location"] = {"city": "Richmond, VA"}
    out = client.put("/api/profile", json=p).json()
    assert out["home"]["lat"] is not None and out["current_location"]["lng"] is not None
    client.put("/api/profile", json=client.get("/api/profile").json() | {
        "home": {"city": "Roanoke, VA"}, "current_location": {"city": "Roanoke, VA"}})


def test_profile_rejects_city_without_state():
    p = client.get("/api/profile").json()
    p["home"] = {"city": "Springfield"}
    r = client.put("/api/profile", json=p)
    assert r.status_code == 422 and "State missing" in r.json()["detail"]
