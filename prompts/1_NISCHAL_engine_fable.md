# Prompt 1 — Nischal (Claude Fable): Decision engine + integration lead

Paste everything below the line into Fable, with the repo open.

---

You are the lead engineer on **LoadCheck**, a VTHacks 14 project (submission Sunday 8:00 AM ET).
Read `SPEC.md` and `AGENTS.md` in full before writing anything. SPEC.md is the contract; three
teammates using Codex are building against it in parallel right now, so never change a model,
route, or function signature without also updating SPEC.md and telling me what changed.

You own the hardest part: the **decision engine** (math, geography, chain optimizer, cash-flow
simulation) and **integration** (FastAPI app, models, wiring teammates' modules together).

## Files you own
`backend/app/models.py`, `main.py`, `profit.py`, `geo.py`, `optimizer.py`, `cashflow.py`,
`backend/tests/test_profit.py`, `test_geo.py`, `test_optimizer.py`, `test_cashflow.py`,
`backend/data/profile.json`, `backend/data/cities.json`, `backend/requirements.txt`, `README.md`.
Do NOT edit `gemini.py`, `nessie.py`, `scripts/`, or `frontend/` except to fix an integration bug,
and tell me when you do.

## Phase 0 — unblock the team (do this first, target 45 minutes)
1. Scaffold `backend/` (FastAPI, Pydantic v2, pytest), `requirements.txt`, `.env` loading.
2. Write `models.py` with every model in SPEC.md exactly.
3. Create **stubs** for every function in "Module interfaces", including `gemini.py` and `nessie.py`,
   returning realistic fake data with the right types. Teammates will replace their own stubs.
4. Write every route in the API table in `main.py`, calling the stubs. `uvicorn app.main:app` must start
   and every route must return valid JSON. Add CORS for `http://localhost:5173`.
5. Tell me to commit and push so teammates can pull. Nothing else matters until this is done.

## Phase 1 — profit.py + geo.py
- `evaluate_load` exactly per SPEC formulas. The golden test must pass to ±0.01.
- Add tests for: zero deadhead, `dispatch_pct = 0`, each verdict branch, missing `loaded_miles_est`
  (computed from geo), and guards (loaded_miles ≤ 0 or rate ≤ 0 raise `ValueError` with a clear message).
- `geo.py`: haversine × 1.2; `resolve()` reads `data/cities.json`, falls back to Nominatim
  (1 req/sec, custom User-Agent, 5 s timeout), writes back to the cache, and returns a warning
  instead of guessing when the state is missing or the lookup fails. Pre-fill `cities.json` with
  every city in `seed_loads.json`. The network call must be isolated so tests never hit the network.

## Phase 2 — optimizer.py (the core; take the most care here)
Implement `best_chains` per SPEC: DFS, chains of 1–3, 250-mile deadhead prune, pickup windows
(wait if early), 2 h load and 2 h unload, `delivery_by` deadlines, simplified HOS (11 h driving,
then a 10 h rest inserted before any drive that would exceed it), trailer-type filter, no reuse.
- Score = sum of leg net profits − cost of the empty drive home. Also compute `days` and `net_per_day`.
- Fill `schedule` and `feasible_notes` (e.g. "Waited 3.0 h for pickup window at L014",
  "10-h rest inserted before L022").
- Return top 3 **distinct** chains: no two results may share the same first load (otherwise the
  top 3 are near-duplicates and the demo looks thin).
- Prefer chains ending ≤ 150 mi from home; if none, return the best anyway with a note.
- Tests: a hand-built 4-load fixture where you know the right answer; a chain that is infeasible only
  because of HOS; one that is infeasible only because of a pickup window; one where waiting makes it
  feasible; runtime under 1 s on the 60-load board (assert it).
- Write a short docstring explaining the search and the pruning; I have to explain it to judges.

## Phase 3 — cashflow.py
`simulate` per SPEC: start from the balance, subtract each leg's fuel cost on its pickup day, subtract
bills on due dates, add pay on `delivered_at + payment_terms_days`. Track the lowest balance and date.
If it goes negative, re-simulate with quick pay on the **fewest loads needed** (greedy: earliest-paying
load first), report `quick_pay_fixes_it` and `quick_pay_cost`. `timeline` is one entry per event, in
date order, with running balance, ready for a chart. Test: a case that dips negative on the 1st because
of the truck payment and is fixed by quick pay on one load.

## Phase 4 — integration (Saturday, from ~11 AM)
- As each teammate replaces a stub, run the full flow: `/extract` → `/evaluate` → `/chains` →
  `/cashflow` → `/explain`. Fix any mismatch at the boundary and tell the owner.
- Add `GET /api/health` that reports which modules are live vs. stub/fixture (helps during the demo).
- Add `scripts/demo_check.py` that calls every route in demo order and prints PASS/FAIL. We run it
  before every rehearsal.

## Phase 5 — the demo scenario (Saturday 4–6 PM)
Help me tune `seed_loads.json` so the story is clean: my dad's real bad load evaluates to about
$0.50/mi true net, and the best 3-load chain from his location earns clearly more and ends near
home, with at least one visible rest stop. Do NOT change the formulas to make the story work; only
change data, and keep every load's `source` as "simulated".

## Working style
- Work in small steps. After each phase, show me the test output and a 5-line summary of what the
  code does and why, so I can explain it without reading every line.
- If something in SPEC.md is ambiguous or wrong, stop and tell me instead of guessing.
- No new dependencies without a reason.
