# LoadCheck: status and handoff

_Last updated: Sat Sep 19, 2026, ~9 PM. Submit Sun 7:15 AM ET (hard stop 8:00)._

Read this first when picking the work back up. It records what's done, what was decided (so nobody re-asks),
what's waiting on whom, and what to do next.

## Where things are
- Repo: https://github.com/VTHACKATHON/VTHACKS · local `~/Documents/CS/VTHACKS`. CI (`tests / backend`) runs pytest
  on every PR and push to main.
- `main` is green: **105 tests**, `demo_check` **15/15**, `npm run build` passes.
- `/api/health`: profit, geo, optimizer, cashflow, **nessie = live**, gemini = **stub** (until #20 lands).
- **The demo runs locally. We are not deploying** (decided Sat 9 PM). The code for hosting exists and works, but
  nothing is online; there is no URL to keep alive and no domain.
- **Capital One (Nessie) is the prize we're going for.** MLH Gemini is secondary; GoDaddy dropped.

## How to run it
**One server (what the demo uses):**
```bash
cd ~/Documents/CS/VTHACKS/frontend && npm run build        # only after a UI change
cd ~/Documents/CS/VTHACKS/backend && source .venv/bin/activate
uvicorn app.main:app --port 8000                            # http://localhost:8000 = whole app
```
**Two servers (while developing):** `uvicorn app.main:app --reload` and, in another tab,
`cd frontend && npm run dev` → http://127.0.0.1:5173.

Demo-day checklist, failure table and the numbers judges ask about: **`docs/RUNBOOK.md`**.

## Merged today (Sat)
| PR | What |
|---|---|
| #8, #16 | Frontend review fixes; demo polish (bad-load example, "Find a better run", run timeline) |
| #9–#11 | Nessie: seed script, recorded fixture, live client with fixture fallback |
| #17 | **Decision 1**: red on the road — $2,500 start, truck payment on the 22nd, cash flow = this trip only, `CashflowCheck.later`; live Nessie re-seeded (new customer) |
| #18 | **Feature A**: money on the map — `balance_along_route`, route colored green/amber/red, ⛽🧾💵 markers, balance strip, cash flow auto-loads |
| #19 | **Feature B**: Capital One advance — Nessie deposit + repayment bill, `/api/advance`, `/api/demo/reset-bank`, two-step confirm on "Accept bank costs" |
| #21 | Place forms take a city only (backend resolves coordinates) |
| #22 | Profile: "How you get paid" (broker net-30 vs dispatcher weekly) + "my rule: minimum posted $/mi" |
| #23 | `docs/FRONTEND_NOTES.md` for the frontend teammate |
| #24 | **Map-first redesign** (Codex): full-screen map workspace, offline map toggle, API error/reconnect state, accessibility, phone layout |
| #25 | `/api/health` reports the bank source it can actually reach (was saying "fixture" while live) |
| #26, #27, #28 | Hosting groundwork: env-var secrets, one server (API serves `frontend/dist`), read-only bank mode, restart recovery, `docs/RUNBOOK.md`. Unused for now — we demo locally |
| #30 | Pitch copy restored on top of the redesign; app opens on Check a load |

Closed unused: #29 (keep-alive ping — only needed if we deploy).

## Decisions already made (don't re-ask)
- **Decision 1 = red on the road.** Start balance **$2,500**, truck payment due the **22nd**, cash flow covers
  **this trip only** (today → home); money that arrives later is listed in `later`, not counted. Reason: over the
  full horizon the balance hits −$2,729 on Oct 22, because one 2.6-day run can't pay a month of bills.
- **Feature B is a "Capital One advance"**, not broker quick pay: pending Nessie deposit on delivery day
  (`rate − dispatch − 3% fee`), repaid by a pending Nessie bill on the broker's pay date. Net cost = the fee.
- **Dad's data is dropped** from the app; the simulated story stays. His real answers are **pitch material**:
  driving since 2014, owns his truck, dispatcher pays **weekly** and takes **7%**, he only takes loads over
  **$3/mi posted**, when short he **borrows from his dispatcher or family**, and the hardest part is **waiting for a
  load**. `profile.min_posted_cpm = 3.00` and the `pays_weekly` switch exist so both setups can be shown in Q&A.
- **No deployment.** Local demo only.
- **Keep the redesigned UI**, with the pitch copy restored (#30).
- Clock: `DEMO_NOW=2026-09-21T06:00`. HOS: 11 h driving / 10 h rest, waits ≥10 h count as rest. `Chain.days` =
  start → home. Losing runs only fill leftover slots. 150-mi home rule stays. `cashflow.py` stays pure; only
  `nessie.py` talks to the bank; numbers never come from Gemini; SPEC.md first for any model/route change.

## Demo story (current numbers, from demo_check)
- **Bad load:** Greensboro, NC → Jacksonville, FL, $1,200 flat: **$2.43/mi posted → $0.55/mi kept**, net $326,
  "negotiate", and **"below your $3.00/mi rule"**.
- **Best run:** L027 Roanoke→Atlanta → L058 Knoxville→Baltimore → L012 Hagerstown→Roanoke: **$1,496**, 2.6 days,
  $574/day, ends at home, 2 visible 10-h rests.
- **Cash (this trip):** starts **$2,500**; the **$2,150 truck payment posts Sep 22 near Rogersville, TN** while he's
  hauling L058 → **−$313**, low **−$494** on Sep 23.
- **Capital One advance on L027:** **+$1,044** on delivery day (Sep 21), fee **$36**, repaid $1,080 on Oct 21 when
  Blue Ridge pays → Sep 22 **$731**, Sep 23 **$550**, map all green, deposit + bill ids shown on screen.

## Known risks
- **Gemini is a stub** until #20 merges *and* a `GEMINI_API_KEY` is in `.env`. Today, anything pasted that doesn't
  mention Greensboro comes back as a canned Roanoke → Charlotte load. A judge who pastes their own offer will see it.
- The redesigned UI **froze once for ~30 s on first load** (heavy first map paint). Not reproducible; wait a beat
  after opening before clicking.
- **Phone layout never checked on a real phone** (the CSS has a proper mobile sheet; nobody has seen it).
- **Pasted loads live in memory**: restart the backend and `/api/chains` 404s for them. Paste again.
- Rehearsals write real deposits into the Nessie sandbox — **click "Reset demo ↺" before judging**.

## Waiting on
| Who | What |
|---|---|
| Ben | PR **#20** (Gemini extraction): my fix-ups are pushed; he needs one live test with his `GEMINI_API_KEY`, then merge. Also `explain()` / `counter_message()` still templates |
| Nihal | Merge #30; timed rehearsal; Devpost draft (title, story, tags Capital One + Gemini); decide on Feature C |
| Frontend teammate | `docs/FRONTEND_NOTES.md`: phone check, advance-card polish |

## Next steps (in order)
1. **Merge #30** (pitch copy) and pull `main`.
2. **Gemini #20**: get Ben's key into `.env`, test a real pasted offer, flip `gemini.STATUS` to `"live"`, merge.
   This is the one thing a judge can break by trying the app themselves.
3. **Rehearse**: 4 minutes, timed, twice. Story: bad load → better run → red in Tennessee → advance → green.
   Reset demo between runs.
4. **Devpost**: title, one-line pitch, the story, screenshots/video, tag Capital One and Gemini. No "Try it" link
   (local only) — record a 30-second screen capture instead.
5. Optional if time remains: **Feature C** (receipt photo → Gemini reads it → Nessie purchase → real spending
   profile; issue #15, design in `docs/CAPITAL_ONE_FEATURES.md`), or the AI follow-up questions idea
   (ask about lumper/detention fees and extra empty miles, then re-run the verdict).
6. Sun 6 AM: Wi-Fi-off run-through (the map has an offline toggle). Sun 7:15 AM: submit.
