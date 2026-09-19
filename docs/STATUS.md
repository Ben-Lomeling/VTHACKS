# LoadCheck: status and handoff

_Last updated: Sat Sep 19, 2026 (afternoon, after the Capital One judges). Deadline: submit Sun 7:15 AM ET (hard stop 8:00)._

Read this first when picking the work back up. It records what's done, what decisions were made (so nobody
re-asks), what's waiting on whom, and what to do next.

## Where things are
- Repo **moved** to https://github.com/VTHACKATHON/VTHACKS (old `Ben-Lomeling/VTHACKS` URL redirects). Local:
  `~/Documents/CS/VTHACKS`. Update the remote once: `git remote set-url origin https://github.com/VTHACKATHON/VTHACKS.git`.
- `main` @ `e109eb9` (PR #7). CI (`tests / backend`) runs pytest on every PR and push to main.
- **Open PRs, merge in this order** (Nihal merges; the assistant is not allowed to merge):
  **#8** review fixes + this file → **#12** demo polish + ideas docs (stacked on #8; retargets to main when #8's branch is
  deleted) → **#9** Nessie seed → **#10** Nessie fixture → **#11** Nessie client (its CI is red alone only because it needs
  #10's fixture; all three merged together: **82 tests pass, demo_check 15/15**, bank $3.92/gal, $0.27/mi, $3,315/mo).
- On `main` today: 56 tests / 15/15; gemini + nessie = stub. After the merges: 82 tests, nessie = live (fixture fallback).
- **Capital One (Nessie) is the main prize focus.** Also enter MLH *Best Use of Gemini API* and *GoDaddy domain*.
  Deloitte's challenge (campus AI agent) doesn't fit; skip.

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

## Capital One judges' feedback (Sat afternoon) → next features
They **don't want an average banking/finance app**; they want a **creative, meaningful use of Nessie**. Plan: turn the
trucker's bank account into a **map of the road ahead**. Full design: **`docs/CAPITAL_ONE_FEATURES.md`**. Build order:
1. **A: Money on the map**: route colored green/amber/red by projected balance; money markers.
2. **B: Get paid early**: tap on a red stretch → **creates a Nessie deposit** → route turns green.
3. **C: Receipt photos**: Gemini reads a receipt → confirm → **saved as a Nessie purchase** → real spending profile (fuel $/mi, food $/day).
**Decision 1 must be made first** (in that doc): with today's data the route never turns red (the dip is Oct 5, after
the trip). Recommended: truck payment due the 22nd, start balance $2,500, instant pay on delivery.

## Ideas (not started)
- Real data sources (EIA diesel, FMCSA broker check, OpenRouteService miles, USDA truck rates): see `docs/REAL_DATA_IDEAS.md`.

## Waiting on
| Who | What |
|---|---|
| Dad | The bad load (offer text, pickup/delivery, where he was, rate, terms, what he actually made), real costs (home city, trailer, MPG, diesel, truck payment, insurance, maintenance, dispatcher %, miles/month, target $/mi), 5 offers + 2 screenshots, 15–20 s video; and whether he needs runs to end near home |
| Gemini teammate | Replace `gemini.py` stub (extract, explain + number check, counter message) → PR on `gemini/...` |
| Nessie worker | Follow-ups on #11: cache live snapshot (slow Wi-Fi = up to 5 s per call), start STATUS as "fixture" until a live call works. Then Feature B/C Nessie writes (`create_deposit`, `create_purchase`, food/parking merchants) |
| Nihal | Merge #8 → #12 → #9 → #10 → #11; `NESSIE_API_KEY` in root `.env` on the demo laptop; Decision 1 |
| Frontend teammate | Pull `frontend/review-fixes` once merged; offline map tiles or no-tile fallback |
| Ben | Protect `main` (message drafted in chat: require PR, 0 approvals, Code Owners review off, required check `backend`, no strict up-to-date) and add collaborators |

## Next steps (in order)
1. Nihal merges #8 → #12 → #9 → #10 → #11. Pull `main`; `pytest -q` (82), `demo_check` (15/15), `npm run build`; click through.
2. Decision 1 (docs/CAPITAL_ONE_FEATURES.md), then **Feature A: money on the map**. Demo-ready checkpoint.
3. **Feature B: get paid early** (Nessie deposit write + reset).
4. **Feature C: receipt photos** (Gemini read + Nessie purchase + food_per_day).
5. Dad's data swap: `profile.json`, prewarm his cities, `BAD_LOAD`, board re-tune (keep `source: simulated`).
6. Gemini PR when it lands (extract/explain/counter; explain the whole run; format negatives as -$0.02).
7. Deploy + free MLH domain (one permanent link for friends + Devpost "Try it"). Needs Nihal to sign in to the hosts.
   A Cloudflare quick tunnel was tried and blocked by the permission classifier; needs Nihal's explicit OK.
8. Sat evening: backup demo video, README GIF, timed 4-minute rehearsal. Sun 6 AM: Wi-Fi-off run-through (map tiles
   need internet; Nessie + cities fall back offline). Sun 7:15 AM: submit on Devpost (tag Capital One, Gemini, GoDaddy).

## Done today (Sat Sep 19)
- Frontend verified on the live backend; fixes (#8); demo polish (#12): bad-load example, stub list hidden (`?dev`),
  "Find a better run", offer-vs-best-run card, run timeline, `/extract` resolves coordinates.
- Nessie PRs #9–#11 reviewed (see above). Real-data ideas: `docs/REAL_DATA_IDEAS.md`. Sponsor research (Capital One =
  focus). Judge cheat sheet + Capital One questions given to Nihal in chat. Node 26, gh (logged in as pradhannihal),
  cloudflared installed via brew.

## Useful commands
```bash
cd ~/Documents/CS/VTHACKS/backend && source .venv/bin/activate
pytest -q                                   # 56 on main today; 82 after the Nessie PRs
uvicorn app.main:app --reload               # API on :8000, docs at /docs
cd .. && python scripts/demo_check.py --in-process   # 15/15
python scripts/prewarm_cities.py "City, ST"          # cache cities for offline
python scripts/export_api_samples.py                 # refresh docs/api-samples/

# frontend (Node 22.18+; installed Node 26 via brew)
cd ~/Documents/CS/VTHACKS/frontend && npm ci
npm run dev                                  # http://127.0.0.1:5173, backend must be on :8000
npm run build                                # tsc + vite build
```
