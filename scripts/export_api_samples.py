"""Save one real response per API route to docs/api-samples/ (frontend mocks should match these shapes).

  python scripts/export_api_samples.py
Runs in-process against the current backend (stubs included), so re-run after modules go live.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

OUT = ROOT / "docs" / "api-samples"
BAD_LOAD = {"id": "DEMO-BAD", "origin": {"city": "Greensboro, NC"}, "destination": {"city": "Jacksonville, FL"},
            "rate_usd": 1200, "trailer_type": "dry_van", "broker": "Coastal Brokerage", "source": "pasted"}


def save(name: str, request, response) -> None:
    body = {"request": request, "response": response.json(), "status": response.status_code}
    (OUT / f"{name}.json").write_text(json.dumps(body, indent=2) + "\n")
    print(f"{response.status_code}  {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = TestClient(app)
    save("GET_health", None, c.get("/api/health"))
    save("GET_profile", None, c.get("/api/profile"))
    save("GET_board", None, c.get("/api/board"))
    save("GET_costs_from_bank", None, c.get("/api/costs/from-bank"))
    save("POST_extract", {"text": "GREENSBORO NC -> JACKSONVILLE FL $1200 all in"},
         c.post("/api/extract", data={"text": "GREENSBORO NC -> JACKSONVILLE FL $1200 all in"}))
    econ = c.post("/api/evaluate", json={"load": BAD_LOAD})
    save("POST_evaluate", {"load": BAD_LOAD}, econ)
    save("POST_offers", {"loads": [BAD_LOAD]}, c.post("/api/offers", json={"loads": [BAD_LOAD]}))
    req = {"seed_load_ids": ["DEMO-BAD"], "include_board": True}
    chains = c.post("/api/chains", json=req)
    save("POST_chains", req, chains)
    best = chains.json()[0]
    cf = c.post("/api/cashflow", json={"chain": best})
    save("POST_cashflow", {"chain": "<first item of POST_chains response>"}, cf)
    ex = {"economics": econ.json(), "chain": best, "cashflow": cf.json()}
    save("POST_explain", {"economics": "...", "chain": "...", "cashflow": "..."}, c.post("/api/explain", json=ex))
    save("POST_counter_message", {"economics": "<POST_evaluate response>"},
         c.post("/api/counter-message", json={"economics": econ.json()}))
    bad = c.post("/api/evaluate", json={"load": {**BAD_LOAD, "rate_usd": 0, "loaded_miles_est": 300}})
    save("ERROR_evaluate_422", "rate_usd = 0", bad)


if __name__ == "__main__":
    main()
