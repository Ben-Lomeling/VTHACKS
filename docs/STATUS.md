# LoadCheck: status and handoff

_Last updated: Fri Sep 18, 2026 (night). Deadline: submit Sun 7:15 AM ET (hard stop 8:00)._

Read this first when picking the work back up. It records what's done, what decisions were made (so nobody
re-asks), what's waiting on whom, and what to do next.

## Where things are
- Repo: https://github.com/Ben-Lomeling/VTHACKS (Ben is admin; Nischal merges). Local: `~/Documents/CS/VTHACKS`.
- `main` @ `764b1a8`. CI (`tests / backend`) runs pytest on every PR and push to main.
- Health: **56 tests pass**, `python scripts/demo_check.py --in-process` → **15/15**.
- `/api/health`: profit, geo, optimizer, cashflow = **live**; gemini, nessie = **stub**.

## Done (merged PRs)
| PR | What |
|---|---|
| (direct) | Phase 0 scaffold: FastAPI app, every SPEC route + `/api/health`, `models.py`, stubs for all 6 modules, README teammate quick-start, PR template, prompts' "Before you start" blocks |
| (web UI) | CI workflow `.github/workflows/tests.yml` |
| #1 | `profit.py` (SPEC formulas, golden test ±0.01) + `geo.py` (haversine ×1.2, cached `resolve()` with Nominatim fallback), `cities.json` prewarmed |
| #2 | `optimizer.py`: DFS over 1–3 load runs, pickup windows, deadlines, simplified HOS, 250-mi prune, top 3 distinct first loads, 150-mi home rule |
| #3 | `cashflow.py`: fuel on pickup day, bills on due dates, pay on delivery + terms, greedy quick-pay fix |
| #4 | `scripts/demo_check.py` + demo scenario data (L027, L039, L059 rewritten; all still `simulated`) |
| #5 | `docs/api-samples/`, `scripts/export_api_samples.py`, `scripts/prewarm_cities.py`, README architecture + engine explainer |
| #6 | Losing runs fill leftover slots (`losing`, `losing_reason`), README "Known simplifications", pitch line fixed, CODEOWNERS = `* @pradhannihal` |

## Decisions already made (don't re-ask; all in SPEC.md)
- **Clock:** `DEMO_NOW` in `.env` (default `2026-09-21T06:00`) sets chains' start time and cash-flow "today".
- **Pasted loads** are remembered in memory by `/evaluate` and `/offers`; `/chains` finds them by `seed_load_ids` (404 if unknown). They're candidates, not forced first legs.
- **HOS:** 11 h driving then 10 h rest; long drives split mid-drive; a wait ≥ 10 h counts as rest. Not modeled: 14-h window, 30-min break, 70-h cap.
- **`Chain.days`** = start until arrival back home (includes rests and the home deadhead). Ranking stays by **total profit**; `days` and `net_per_day` are on every run.
- **Losing runs** (profit ≤ 0) only fill slots profitable runs leave open (max 3 total), must still end ≤ 150 mi from home, carry `losing: true` + `losing_reason`.
- **150-mi home rule** stays for now (asking Dad whether he needs to end near home).
- **Cash flow:** deposit = rate − dispatch fee; quick pay = paid delivery + 2 days, fee = rate × `quick_pay_fee_pct`; timeline is the original run (shows the dip); money out before money in on the same day.
- **Profile** accepts any US city (backend resolves coordinates; 422 if it can't place it).
- **Deps added:** `python-multipart`, `python-dotenv`. Python 3.11+ (local venv is 3.12).
- **geo purity:** math is pure; only `geo.resolve()` touches `cities.json` and the network.

## Demo story (current numbers, from demo_check)
- **Bad load (stand-in until Dad's text):** Greensboro, NC → Jacksonville, FL, $1,200 flat: $2.43/mi posted → **$0.55/mi** true, $326 net, "negotiate".
- **Best run from Roanoke:** L027 Roanoke→Atlanta → L058 Knoxville→Baltimore → L012 Hagerstown→Roanoke: **$1,496**, 2.6 days, $574/day, ends home, 2 visible 10-h rests.
- **Cash flow ($3,800 start):** negative on **Oct 5** (insurance), bottoms at **−$359 on Oct 15**, first broker pays Oct 21. Quick pay on the Atlanta load fixes it for **$36**.
- Pitch line updated in SPEC.md and in the team game-plan doc to match these numbers.

## Frontend check (Fri night)
Branch `origin/frontend/loadcheck-ui`, 1 commit, **no PR opened yet**. Touches only `frontend/` (good).
- **Present:** all 3 screens; confirm card with low-confidence highlighting and warnings; posted rate struck
  through vs. true net; cost bars; verdict; counter-offer + copy message; rank offers; map (solid loaded, dashed
  empty, purple dashed home, P/D pins); chain cards with $/day, days and notes; "Simulated load board" badge;
  cash-flow chart with zero line and bill markers; bank diff with Accept / Keep mine; Reset demo; `/api/health`
  banner; readable error messages; mock mode via `VITE_USE_MOCKS`.
- `types.ts` matches `models.py` field for field **except** the new `Chain.losing` / `losing_reason` (added in #6
  after the frontend was written) → no "losing" badge yet.
- Its `frontend/README.md` is out of date (says backend is all stubs, 8 tests, no golden test).
- **Not verified by us:** build and run. This Mac has **no Node** (needs Node ≥ 22.18). Install with
  `brew install node`, then `cd frontend && npm ci && npm run dev` with the backend running.
- **Risk:** map tiles come from OpenStreetMap over the internet, so the map will be blank in a Wi-Fi-off demo.
  Decide: accept it, cache tiles, or show the route without tiles.

## Waiting on
| Who | What |
|---|---|
| Dad | The bad load (offer text, pickup/delivery, where he was, rate, terms, what he actually made), real costs (home city, trailer, MPG, diesel, truck payment, insurance, maintenance, dispatcher %, miles/month, target $/mi), 5 offers + 2 screenshots, 15–20 s video; and whether he needs runs to end near home |
| Gemini teammate | Replace `gemini.py` stub (extract, explain + number check, counter message) → PR on `gemini/...` |
| Nessie teammate | Seed script working, fixture recorded, `nessie.py` live → PR on `nessie/...`; Capital One challenge statement |
| Frontend teammate | Open the PR for `frontend/loadcheck-ui`; add `losing` / `losing_reason` to `types.ts` + a losing badge; refresh their README |
| Ben | Protect `main` (message drafted in chat: require PR, 0 approvals, Code Owners review off, required check `backend`, no strict up-to-date) and add collaborators |

## Next steps (in order)
1. Install Node, run the frontend against the real backend, fix any integration bugs (tell the owner).
2. Review + merge the frontend PR once opened; then Gemini and Nessie PRs as they arrive.
3. Phase 4: full flow `/extract → /evaluate → /chains → /cashflow → /explain` on live modules; `demo_check` must stay 15/15.
4. Dad's data: update `profile.json`, run `python scripts/prewarm_cities.py "<his cities>"`, swap `BAD_LOAD` in `demo_check.py` and the demo text for his real offer, re-tune the board (data only, keep `source: simulated`) so it lands near $0.50/mi.
5. After Nessie is live: re-check the cash-flow pitch line numbers (they depend on the real balance and bills).
6. Sat 12 PM checkpoint: paste → confirm → result on the real backend. Sat 4 PM: every MVP feature on real data. **Sat 6 PM: feature freeze.**
7. Sat evening: backup demo video, README GIF, timed 4-minute rehearsal. Sun 6 AM: Wi-Fi-off run-through. Sun 7:15 AM: submit.

## Useful commands
```bash
cd ~/Documents/CS/VTHACKS/backend && source .venv/bin/activate
pytest -q                                   # 56 should pass
uvicorn app.main:app --reload               # API on :8000, docs at /docs
cd .. && python scripts/demo_check.py --in-process   # 15/15
python scripts/prewarm_cities.py "City, ST"          # cache cities for offline
python scripts/export_api_samples.py                 # refresh docs/api-samples/
```
