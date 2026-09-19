# Capital One features: "the road ahead" (plan, not built yet)

_Written Sat Sep 19, 2026 after talking to the Capital One judges. Build order: **A → B → C**, so there is
something demo-ready early even if time runs out._

## Why
The Capital One judges said they **don't want an average banking/finance app**. They want a **creative, meaningful
use of Nessie**. Our answer: **turn a trucker's bank account into a map of the road ahead.** Truckers often can't tell
whether they can afford a trip before they get paid (brokers pay 30+ days after delivery). Nessie is used both ways:
we **read** his balance, bills and spending, and **write** deposits and purchases back. It's also Dad's story.

**Pitch line:** *"Your bank shows what you spent. LoadCheck shows where on the road you'll run out of money, and
lets you fix it before you leave."*

## ✅ Decision 1 (decided Sat Sep 19, 3 PM): red on the road, trip-only cash flow, Capital One advance
Nihal's choices (full list in `docs/STATUS.md`):
- **Option 1: red on the road.** Truck payment due on the **22nd** (was the 1st), starting balance **$2,500** (was $3,800).
- **Cash flow covers this trip only** (today → home). Checked in code: over the full horizon the balance falls to
  −$2,729 on Oct 22, because one 2.6-day run ($3,375 take-home) can't pay a month of bills ($3,315 + diesel), and
  October's truck payment lands a day before the last brokers pay. His next runs cover October; broker pay and
  advance repayments after he's home are listed in a new `later` field, not counted in the balance. See SPEC.md Feature 2.
- **Feature B is a "Capital One advance"**, not broker quick pay: on delivery day Nessie gets a **deposit** of
  `rate − dispatch − 3% fee`; a Nessie **bill** repays `rate − dispatch` on the broker's pay date. Net cost = the fee.
- **Minimum to submit: A + B.** C is a bonus. Dad's data is dropped; the simulated story stays.

Verified numbers (in code, fixture with the Option 1 changes):

| Date | Event | Balance | With advance on L027 |
|---|---|---|---|
| Sep 21 | Start | $2,500 | $2,500 |
| Sep 21 | Diesel L027 (−$245) · L027 delivered 7:22 PM | $2,255 | + advance $1,044 → $3,299 |
| Sep 22 | Diesel L058 (−$418) + **truck payment (−$2,150)**, hauling through TN | **−$313** 🔴 | $731 🟢 |
| Sep 23 | Diesel L012 (−$181), home that night | −$494 | $550 |
| Oct 21 | (later) Blue Ridge pays L027 $1,080 → repays the advance | | net $0 |

Option 1 touches: the Nessie seed + fixture (bill day, balance), `cashflow.py` (window + advance on delivery day +
`later`), `models.py`/`types.ts` (`later`), `scripts/demo_check.py`, pitch numbers in SPEC/README/STATUS, and
`docs/api-samples/`.

## Feature A: Money on the map (build first)
**What the judge sees:** on Plan my run, the route line is colored by his projected balance: **green** (fine),
**amber** (under a buffer, e.g. $500), **red** (overdrawn). Markers show where money leaves (⛽ fuel, 🍔 food,
🧾 bill) and where it arrives (💵 broker pay, possibly weeks later, shown in the timeline). Hovering a stretch shows the balance.

**Backend (pure; no I/O in `cashflow.py`)**
- New pure function in `backend/app/cashflow.py`: `balance_along_route(chain, loads_by_id, start_balance, bills, today,
  quick_pay=set()) -> list[dict]`. It walks the optimizer's `chain.schedule` (depart / pickup / delivered per leg) and the
  legs' coordinates, and emits ordered route points `{at, lat, lng, balance, label, kind}` where money moves:
  fuel at each pickup (current model), bills on their due date at wherever the truck is then (interpolate between
  schedule times), food per day at each midnight (0 until Feature C supplies it). Reuse `_events()` / `_run()` so the chart,
  the table and the map always agree.
- SPEC change (backward compatible): add `route: list[dict] = []` to `CashflowCheck` in `models.py` + `frontend/src/types.ts`;
  `/api/cashflow` fills it. Nothing else in the contract changes.
- Tests (`backend/tests/test_cashflow.py`): route balances match the timeline's balances at the same events; red appears
  exactly where the timeline first goes below 0; quick-pay set removes the red.

**Frontend**
- `frontend/src/components/RouteMap.tsx`: when a `CashflowCheck` with `route` exists, draw each stretch as its own
  `Polyline` colored by balance (keep the loaded/empty dash styles as the line pattern, color = money). Money markers
  as small `divIcon`s. Legend: "Green = covered · Red = overdrawn".
- `frontend/src/components/RunTimeline.tsx`: add a thin balance strip under the time bar with the same colors.
- `frontend/src/App.tsx`: fetch cash flow automatically when a run is selected (today it's a button), so the map is
  colored without an extra click.

## Feature B: Capital One advance (build second)
**What the judge sees:** a red stretch has a **"Get a Capital One advance"** button. Tapping it **creates a real deposit
in Nessie** (plus the repayment bill on the broker's pay date), and the map repaints green. The Nessie deposit is visible (show "Deposit created in Capital One · id …").

**Backend**
- `backend/app/nessie.py` (Nessie owner): `create_deposit(amount, on: date, description) -> dict` and
  `delete_deposit(id)`: `POST /accounts/{account_id}/deposits` (`medium: "balance"`, `transaction_date`, `amount`,
  `description: "QUICK PAY L027 (Blue Ridge Logistics)"`), `DELETE /deposits/{id}`. Offline: record it in memory +
  mark `source: "fixture"` so the demo still works with Wi-Fi off. **Verify:** does Nessie accept a future
  `transaction_date`? If not, post it dated today and keep the planned date in our own record.
- New route `POST /api/quick-pay` `{chain, load_id}` → creates the deposit, adds `load_id` to the quick-paid set, returns the
  updated `CashflowCheck` (timeline + route). New `POST /api/demo/reset-bank` deletes deposits we created (for rehearsals;
  wire it into the existing "Reset demo" button).
- `cashflow.simulate` already models quick pay (`_events(..., quick_pay)`); reuse it. Don't add a second path.
- SPEC: add both routes to the API table + a `QuickPayRequest {chain: Chain, load_id: str}` model.
- Tests: route calls a fake `nessie.create_deposit` (monkeypatch); returned cash flow has no red; reset deletes.

**Frontend:** button on the red stretch + next to the cash-flow notice; confirm dialog as an inline card (no browser
`confirm()`); after success, repaint map + chart and show the Nessie deposit id.

## Feature C: Receipt photos (build last)
**What the judge sees:** "Add a receipt" → take/upload a photo → AI reads **amount, category (fuel / food / parking /
repairs), date, gallons** → driver confirms (same confirm-first pattern as load offers) → **saved as a real Nessie
purchase** → his spending profile updates ("food: $38/day, fuel: $0.59/mi") and Check a load uses those numbers.

**Backend**
- `backend/app/gemini.py` (Gemini owner): `read_receipt(image_bytes, mime) -> ReceiptDraft` (AI reads, never computes).
- `backend/app/nessie.py`: `create_purchase(category, amount, on, description)` against the seeded merchant for that
  category (add **food** and **parking** merchants to the seed + fixture). Fuel descriptions keep the
  `"DIESEL 112.4 GAL @ 3.92"` format so the existing gallons parser in `get_costs_from_bank` keeps working.
- Routes: `POST /api/receipts/read` (multipart image → `ReceiptDraft` with per-field confidence),
  `POST /api/receipts` (confirmed draft → purchase id + updated costs-from-bank).
- New profile field `food_per_day: float = 0` (SPEC change). Used by `cashflow` (per day on the road) and in the chain
  totals (days × food). **This changes the demo numbers and possibly the golden test**; decide whether food counts
  in per-load economics or only in runs/cash flow (recommend: runs + cash flow only, so the golden test stays).
- Tests: parse + category mapping on sample drafts; purchase body shape (MockTransport); food_per_day flows into cash flow.

**Frontend:** "Add a receipt" card on Setup (reuse the screenshot upload + confirm-card components from Check a load),
a "Your real spending" panel (fuel $/mi, food $/day, from N receipts), and a toast "Saved to Capital One".

## Rules that still apply (AGENTS.md)
- Numbers come from code (`profit` / `optimizer` / `cashflow` / `nessie`), never from Gemini.
- `cashflow.py` stays pure; only `nessie.py` talks to Nessie; every Nessie call falls back to the fixture.
- Every new function gets a pytest; `pytest -q` and `python scripts/demo_check.py --in-process` stay green
  (update demo_check deliberately if Decision 1 = Option 1).
- SPEC.md first for every model/route change; `frontend/src/types.ts` mirrors `models.py`.
- Owners: `gemini.py` = Gemini teammate, `nessie.py` = Nessie worker; tell them what changed in their files.

## Demo script once all three exist (≈60 s of the 4 min)
1. Setup → "Add a receipt" (Love's diesel) → confirm → "Saved to Capital One" → spending updates.
2. Check a load → bad load → "Find a better run".
3. Map: route turns **red in Tennessee** (truck payment lands mid-trip) → **Get paid early** → deposit created in
   Nessie → route turns **green**.
4. Line: *"Capital One already knows his bills. LoadCheck puts them on his map."*
