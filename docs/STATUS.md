# LoadCheck: status and handoff

_Last updated: Sat Sep 19, 2026 (morning). Deadline: submit Sun 7:15 AM ET (hard stop 8:00)._

Read this first when picking the work back up. It records what's done, what decisions were made (so nobody
re-asks), what's waiting on whom, and what to do next.

## Where things are
- Repo: https://github.com/Ben-Lomeling/VTHACKS (Ben is admin; Nischal merges). Local: `~/Documents/CS/VTHACKS`.
- `main` @ `e109eb9` (frontend PR #7 merged). Open: `frontend/review-fixes` (review fixes + this file). CI (`tests / backend`) runs pytest on every PR and push to main.
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
| #7 | Frontend (all 3 screens, map, cash-flow chart, bank diff, mock mode) + losing-run warning. Only touches `frontend/`. |

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

## Frontend check (Sat morning)
PR #7 merged. Node 26 installed (`brew install node`); `npm ci && npm run build` passes. Clicked through every screen
against the live backend: example -> confirm -> $0.88/mi TAKE; plan -> $1,495.84 L027->L058->L012 with map; cash flow
-$359.03 on Oct 15, quick pay $36; bank diff works. No console errors. `types.ts` matches `models.py` incl. `losing`.

Fixed on `frontend/review-fixes` (told the frontend teammate):
- TAKE loads no longer show "Counter at <less than the offer>"; counter message button only on negotiate/skip.
- Cash-flow x-axis is real time (was evenly spaced per event); bill markers actually render as red dots; no duplicate-key warnings.
- Same-city map stops merge into one pin ("H · ● · 1P · 3D"); map card is sticky instead of stretched.
- `frontend/README.md` refreshed (live modules, 56 tests, demo_check 15/15).

Demo polish on `frontend/demo-polish` (stacked on review-fixes):
- "Try an example" = the story's bad load (Greensboro -> Jacksonville, $2.43 -> $0.55/mi, negotiate). The Gemini stub
  returns that load when the text mentions Greensboro; the real Gemini replaces it.
- `/api/extract` now places origin/destination with `geo.resolve` (Gemini gives city names, not coordinates); +1 test.
- Module "stub/live" strip hidden unless `?dev`; "Find a better run ->" button; "This offer vs. your best run" card;
  run timeline (loaded / empty / 10-h rests / home) under the map; miles line rounded.
- For Gemini teammate: the run explanation on Plan explains leg 1 ("take, $1.29/mi"), not the run; format negatives as -$0.02.

**Still open:** map tiles come from OpenStreetMap over the internet -> blank in a Wi-Fi-off demo. Frontend teammate
asked to cache tiles or add a no-tile fallback. Not tested yet: counter message on a negotiate load (Gemini stub always
extracts the TAKE example).

## Waiting on
| Who | What |
|---|---|
| Dad | The bad load (offer text, pickup/delivery, where he was, rate, terms, what he actually made), real costs (home city, trailer, MPG, diesel, truck payment, insurance, maintenance, dispatcher %, miles/month, target $/mi), 5 offers + 2 screenshots, 15–20 s video; and whether he needs runs to end near home |
| Gemini teammate | Replace `gemini.py` stub (extract, explain + number check, counter message) → PR on `gemini/...` |
| Nessie teammate | Seed script working, fixture recorded, `nessie.py` live → PR on `nessie/...`; Capital One challenge statement |
| Frontend teammate | Pull `frontend/review-fixes` once merged; offline map tiles or no-tile fallback |
| Ben | Protect `main` (message drafted in chat: require PR, 0 approvals, Code Owners review off, required check `backend`, no strict up-to-date) and add collaborators |

## Next steps (in order)
1. ~~Install Node, run the frontend against the real backend~~ done Sat AM. Merge `frontend/review-fixes`.
2. Review + merge Gemini and Nessie PRs as they arrive; re-run the frontend against them.
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

# frontend (Node 22.18+; installed Node 26 via brew)
cd ~/Documents/CS/VTHACKS/frontend && npm ci
npm run dev                                  # http://127.0.0.1:5173, backend must be on :8000
npm run build                                # tsc + vite build
```
