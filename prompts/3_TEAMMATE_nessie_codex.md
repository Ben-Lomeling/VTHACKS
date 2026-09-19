# Prompt 3 — Teammate (Codex): Capital One Nessie integration

Paste everything below the line into Codex after pulling the repo.

---

## Before you start (setup done by Nischal — read once)
- Follow **README.md → "Teammates: start here"** for setup, the branch flow and the PR template.
- Your code lives in `backend/app/nessie.py`. For backend modules a **stub** already exists with the frozen signatures
  (get_checking_balance, get_upcoming_bills, get_costs_from_bank, data_source) returning fake data. Replace the insides; keep every signature, model and route exactly.
- When your module is real, set `STATUS = "live"` at the top of the file (it shows in `GET /api/health`).
- Put NESSIE_API_KEY in `.env` (repo root). `data_source()` already exists in the stub; keep it. When the fixture fallback is used, set STATUS to "fixture".
- The backend clock is `DEMO_NOW` in `.env` (default `2026-09-21T06:00`) so the simulated board's dates line up.
- Branch: `nessie/<short-task>`, one small PR per task into `main`, paste `pytest -q` output in the PR. Nischal merges.

You are working on **LoadCheck**, a hackathon project. Read `SPEC.md` and `AGENTS.md` first,
especially the "Capital One Nessie" section. You own `scripts/seed_nessie.py`,
`backend/app/nessie.py`, `backend/data/nessie_ids.json`, `backend/data/nessie_fixture.json`,
and their tests. Do not change any model, route, or signature in SPEC.md's "Module interfaces".
A stub of `nessie.py` already exists; replace its internals, keep its signatures.

Nessie base URL: `http://api.nessieisreal.com`, API key as the `key` query parameter,
from `NESSIE_API_KEY`. Docs: http://api.nessieisreal.com/documentation

## Task 1 — make the seed script work (do this tonight)
`scripts/seed_nessie.py` is an UNTESTED draft. Compare every request body with the Nessie docs,
run it, and fix whatever Nessie rejects. It must create: a customer, a checking account (~$3,800),
6 merchants with categories and geocodes, ~90 days of purchases (diesel with gallons in the
description like "DIESEL 112.4 GAL @ 3.789", tolls, tires, repairs), 3 recurring bills (truck payment
$2,150 on the 1st, insurance $1,100 on the 5th, ELD/phone $65 on the 15th), and past load-pay deposits.
Make it safe to re-run: if `nessie_ids.json` exists, ask before creating a second customer.
Replace the made-up costs with Nischal's dad's real numbers once he sends them.

## Task 2 — record the fixture (immediately after Task 1 works)
`scripts/record_fixture.py`: GET the account, purchases, merchants, bills, and deposits and save the raw
JSON to `backend/data/nessie_fixture.json`. The demo must work with Wi-Fi off.

## Task 3 — `nessie.py`
- A small client with a 5 s timeout. Every public function tries the live API and falls back to the
  fixture on any error, logging which one it used. Expose `data_source() -> "live" | "fixture"`.
- `get_checking_balance() -> float`
- `get_upcoming_bills(days=45) -> list[dict]`: `{payee, amount, due_date}` with real `date` objects,
  expanding recurring bills into each due date inside the window.
- `get_costs_from_bank(profile) -> dict` per SPEC:
  - fuel $/gal = total diesel dollars ÷ total gallons parsed from descriptions (skip any it can't parse,
    and count them in `evidence`)
  - variable $/mi = (tires + repairs + tolls over 90 days) ÷ (profile.miles_per_month × 3)
  - fixed monthly = sum of recurring bill amounts
  - returns `{current: profile, proposed: profile with those three fields replaced and cost_source="nessie",
    evidence: {fuel_gallons, fuel_spend, maintenance_spend, bills: [...], unparsed_count, window_days, source}}`
- Nothing outside `nessie.py` should ever see raw Nessie JSON.

## Task 4 — tests
Test the parsing and cost math using the fixture only (no network): gallons parsing, including a bad
description; recurring bill expansion across a month boundary; the fallback path when the API raises.

## Task 5 — Capital One track (Saturday)
Find the Capital One challenge statement (Discord or their table) and send Nischal a 3-line summary
of what they want. Draft 3 bullets for Devpost explaining exactly which Nessie endpoints we use and why
the bank data changes the driver's decision. Be honest that it's sandbox data we seeded.

## Done means
Seed works, fixture recorded, tests pass without network, the stub is fully replaced, and you can
explain in 30 seconds to a Capital One judge what their API adds. Push to `nessie/...` and ask
Nischal to merge.
