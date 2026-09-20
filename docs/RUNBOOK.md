# Demo-day runbook (print this)

## The three ways to show LoadCheck
| # | How | When to use it | Command / link |
|---|---|---|---|
| 1 | **Live site** | Devpost link, judges on their own phones | `<RENDER URL — fill in>` |
| 2 | **Tunnel from the laptop** | the live site is down | `cloudflared tunnel --url http://localhost:8000` |
| 3 | **Laptop only** | no internet at all | see "Start it locally" |

The live site runs in **demo mode**: an advance there is not written to the bank. **Your laptop writes the real
Capital One deposit during the pitch** — that's the moment judges should see.

## Start it locally (one server)
```bash
cd ~/Documents/CS/VTHACKS/frontend && npm run build        # only if the UI changed
cd ~/Documents/CS/VTHACKS/backend && source .venv/bin/activate
uvicorn app.main:app --port 8000                            # http://localhost:8000 = whole app
```

## 10 minutes before judging
1. Open the live link once (wakes it if it slept).
2. On the laptop: open `http://localhost:8000/api/health` → must show `"nessie":"live"` and `"bank_writes":"on"`.
3. Click **Reset demo ↺** so no advance from a rehearsal is left in the bank.
4. Load the story once: example load → better run → map red → advance → green → **Reset demo** again.
5. Plug in the laptop. Turn off sleep. Close Slack/Discord notifications.

## If something breaks mid-demo
| What you see | Do this |
|---|---|
| Live site spins for ~40 s | It was asleep. Keep talking; it will come up. Or switch to the laptop. |
| "API offline" on the laptop | The backend tab died: rerun the `uvicorn` command above. |
| Map is grey | Click **Use offline map**. The route still colors green/red. |
| Advance says "Demo mode" on the laptop | `NESSIE_API_KEY` missing from `.env`, or `NESSIE_WRITES=off` is set. |
| Map starts green (no red) | A leftover advance: click **Reset demo ↺** and replan. |
| Pasted load 404s after a restart | Paste it again; pasted loads live in memory. |
| Everything is wrong | Quit uvicorn, rerun it, reload the page. Fresh process, clean state. |

## Numbers to know (judges ask)
- Bad load: $2.43/mi posted → **$0.55/mi** kept, net $326. His own rule is $3.00/mi posted.
- Best run: L027 → L058 → L012, **$1,496** in 2.6 days, ends at home.
- Cash: starts **$2,500**; the **$2,150 truck payment on Sep 22** hits in Tennessee → **−$313**, low −$494.
- Capital One advance on L027: **+$1,044** on delivery day, fee **$36**, repaid $1,080 on Oct 21 → run covered.
- Nessie is used both ways: we **read** balance, bills and 90 days of purchases; we **write** the deposit and the
  repayment bill.

## One-liners
- *"Your bank shows what you spent. LoadCheck shows where on the road you'll run out of money — and fixes it before you leave."*
- *"Capital One already knows his bills. LoadCheck puts them on his map."*
