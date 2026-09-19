"""Record raw Nessie responses, atomically, for a genuinely offline demo.

Run with backend/.venv/bin/python scripts/record_fixture.py after seeding.
Only the selected account's merchants are recorded; credentials never are.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data"
BASE = "https://api.nessieisreal.com"


def record(client: httpx.Client, ids: dict, output: Path) -> dict:
    def get(path: str) -> dict | list:
        response = client.get(path)
        if not response.is_success:
            raise RuntimeError(f"GET {path}: HTTP {response.status_code}")
        return response.json()

    path = f"/accounts/{ids['account_id']}"
    snapshot = {"account": get(path)}
    for resource in ("purchases", "bills", "deposits"):
        snapshot[resource] = get(path + "/" + resource)
        if not isinstance(snapshot[resource], list):
            raise ValueError(f"Expected a list for {resource}")
    merchant_ids = {p["merchant_id"] for p in snapshot["purchases"]}
    merchant_ids.update(m["id"] for m in ids["merchants"].values())
    snapshot["merchants"] = [get(f"/merchants/{mid}") for mid in sorted(merchant_ids)]
    if snapshot["account"]["_id"] != ids["account_id"]:
        raise ValueError("Unexpected account in response")
    if abs(float(snapshot["account"]["balance"]) - 3800) > 1:
        raise ValueError("Balance drift: refusing to replace demo fixture")
    snapshot["metadata"] = {"source": "Nessie sandbox; seeded demo data",
        "recorded_at": datetime.now(timezone.utc).isoformat()}
    encoded = json.dumps(snapshot, indent=2) + "\n"
    # Refuse an unexpected echo of any credential anywhere in the response.
    key = str(client.params.get("key", ""))
    if key and key in encoded:
        raise ValueError("Credential detected; refusing to write fixture")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(encoded)
    temporary.replace(output)
    return snapshot


def main() -> None:
    key = dotenv_values(ROOT / ".env").get("NESSIE_API_KEY")
    if not key:
        raise SystemExit("Set NESSIE_API_KEY in the repository root .env.")
    try:
        ids = json.loads((DATA / "nessie_ids.json").read_text())
        if ids.get("state") != "complete":
            raise ValueError("Seed is incomplete")
        with httpx.Client(base_url=BASE, params={"key": key}, timeout=5) as client:
            result = record(client, ids, DATA / "nessie_fixture.json")
    except Exception as exc:
        # Never print an exception URL containing the key.
        raise SystemExit(f"Recording failed ({type(exc).__name__}); existing fixture preserved.") from None
    print(f"Recorded account, {len(result['purchases'])} purchases, "
          f"{len(result['merchants'])} merchants, {len(result['bills'])} bills, "
          f"{len(result['deposits'])} deposits.")


if __name__ == "__main__":
    main()
