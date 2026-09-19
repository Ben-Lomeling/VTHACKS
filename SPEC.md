# LoadCheck — Build Spec (VTHacks 14)

> This file is the contract. Frontend, backend, and every Codex session build against it.
> If you need to change a schema or endpoint, change it HERE first, tell the team, then change code.

## One-line pitch
Paste or screenshot any load offer. LoadCheck tells an owner-operator what he'll actually keep,
finds a better 2–3 load run that ends near home, checks it against his real bank account
(Capital One Nessie), and hands him a counter-offer if the load is worth fighting for.

## Hard rules
1. **Code does all math. Gemini never produces a number we display.** Gemini only (a) extracts
   fields from text/images and (b) writes the explanation from numbers we pass in.
2. **Every extraction goes through an editable confirm screen** before any calculation.
3. **The load board is simulated and labeled "Simulated" in the UI.** Nessie bank data is sandbox data
   we seeded. Say both out loud in the demo.
4. No auth. One hardcoded driver profile (`driver_id = "demo"`).
5. Demo runs on localhost. A recorded backup video exists by Saturday 10 PM.

## Stack
- Backend: Python 3.11+, FastAPI, Pydantic v2, `httpx`, `google-genai` SDK, `pytest`,
  `python-multipart` (needed for the image upload on `/api/extract`), `python-dotenv` (`.env` loading).
- Frontend: React + Vite + TypeScript, Tailwind, `react-leaflet` (OpenStreetMap tiles).
- AI: Gemini API (current Flash model from AI Studio) with structured JSON output.
- Bank: Capital One Nessie API, base `http://api.nessieisreal.com`, key as `?key=` query param.
- Storage: JSON files in `backend/data/`. No database.

## Repo layout
```
loadcheck/
  SPEC.md  AGENTS.md  README.md  .env.example
  backend/
    app/main.py            # FastAPI routes only; no logic      (Owner: NISCHAL)
    app/models.py          # every Pydantic model below         (Owner: NISCHAL)
    app/profit.py          # pure functions: profit math        (Owner: NISCHAL)
    app/optimizer.py       # pure functions: chain search       (Owner: NISCHAL)
    app/cashflow.py        # pure functions: balance simulation (Owner: NISCHAL)
    app/geo.py             # haversine, city lookup, cache      (Owner: NISCHAL)
    app/gemini.py          # extract + explain + counter msg    (Owner: GEMINI teammate)
    app/nessie.py          # Nessie client + costs-from-bank    (Owner: NESSIE teammate)
    data/seed_loads.json   # 60 SIMULATED loads (provided)
    data/profile.json      # demo driver profile
    data/cities.json       # city -> lat/lng cache
    tests/                 # golden tests below MUST pass
  frontend/src/...          #                                    (Owner: FRONTEND teammate)
  scripts/seed_nessie.py    # creates the demo bank customer    (Owner: NESSIE teammate)
  prompts/                  # one kickoff prompt per person
```

## Data models (Pydantic; mirror as TS types in `frontend/src/types.ts`)

```python
class Place(BaseModel):
    city: str            # "Richmond, VA" — always "City, ST"
    lat: float | None = None
    lng: float | None = None

class TruckProfile(BaseModel):
    home: Place
    current_location: Place
    trailer_type: Literal["dry_van", "reefer", "flatbed"]
    mpg_loaded: float = 6.5
    mpg_empty: float = 7.5
    fuel_price: float = 3.80          # $/gal; overwritten by Nessie-derived value when available
    variable_cpm: float = 0.20        # maintenance + tires, $/mile
    fixed_monthly: float = 5000       # truck payment + insurance + permits, $/month
    miles_per_month: float = 10000
    dispatch_pct: float = 0.10        # 0 if self-dispatched
    target_net_cpm: float = 0.75      # driver's minimum acceptable net $/mile
    cost_source: Literal["manual", "nessie"] = "manual"

class Load(BaseModel):
    id: str
    origin: Place
    destination: Place
    pickup_window_start: datetime | None = None   # all `| None` fields default to None (may be omitted)
    pickup_window_end: datetime | None = None
    delivery_by: datetime | None = None
    rate_usd: float                    # TOTAL linehaul pay for the load
    loaded_miles_est: float | None = None  # if missing, computed by geo.py
    trailer_type: str | None = None
    weight_lbs: int | None = None
    commodity: str | None = None
    broker: str | None = None
    payment_terms_days: int = 30
    quick_pay_fee_pct: float = 0.03
    source: Literal["pasted", "screenshot", "simulated"]

class ExtractionResult(BaseModel):
    load: Load
    confidence: dict[str, Literal["high", "low"]]  # per field
    warnings: list[str]    # e.g. "Rate may be per-mile, not total", "State missing for Springfield"

class LoadEconomics(BaseModel):
    load_id: str
    deadhead_miles: float
    loaded_miles: float
    total_miles: float
    posted_rpm: float          # rate / loaded_miles  (what the broker advertises)
    fuel_cost: float
    variable_cost: float
    fixed_cost: float
    dispatch_fee: float
    net_profit: float
    true_net_cpm: float        # net / total_miles  (what the driver actually keeps)
    break_even_rate: float
    counter_offer_rate: float  # rate needed to hit target_net_cpm
    verdict: Literal["take", "negotiate", "skip"]

class Chain(BaseModel):
    loads: list[str]              # load ids in order
    legs: list[LoadEconomics]
    home_deadhead_miles: float
    home_deadhead_cost: float
    total_net_profit: float       # sum of legs minus home deadhead cost
    total_miles: float
    days: float                   # start_time -> arrival back home (incl. rests and the home deadhead)
    net_per_day: float
    ends_at: Place
    feasible_notes: list[str]     # e.g. "10-hr rest inserted before L014"
    schedule: list[dict]          # [{load_id, depart_at, pickup_at, delivered_at}] ISO strings; cashflow uses delivered_at
                                  # delivered_at = arrival at destination + 2 h unload
    losing: bool = False          # true only when total_net_profit <= 0
    losing_reason: str | None = None  # one line, e.g. "Loses $345: 142 empty miles to pickup"

class CashflowCheck(BaseModel):
    starting_balance: float
    lowest_balance: float
    lowest_balance_date: date
    shortfall: bool               # lowest_balance < 0
    quick_pay_fixes_it: bool
    quick_pay_cost: float
    timeline: list[dict]          # [{date, label, amount, balance}] for the chart
```

## The math (profit.py) — pure functions, no I/O

```
total_miles     = deadhead_miles + loaded_miles
fuel_cost       = fuel_price * (deadhead_miles / mpg_empty + loaded_miles / mpg_loaded)
variable_cost   = variable_cpm * total_miles
fixed_cost      = (fixed_monthly / miles_per_month) * total_miles
dispatch_fee    = rate * dispatch_pct
net_profit      = rate - dispatch_fee - fuel_cost - variable_cost - fixed_cost
posted_rpm      = rate / loaded_miles
true_net_cpm    = net_profit / total_miles
costs           = fuel_cost + variable_cost + fixed_cost
break_even_rate = costs / (1 - dispatch_pct)
counter_offer   = (costs + target_net_cpm * total_miles) / (1 - dispatch_pct)
verdict         = "take" if true_net_cpm >= target_net_cpm
                  else "negotiate" if counter_offer <= rate * 1.20
                  else "skip"
```
Round only for display. Keep full precision internally.

### Golden test (must pass exactly, ±0.01)
Profile defaults above. Load: rate $1,200, loaded 500 mi, deadhead 100 mi.
| field | expected |
|---|---|
| posted_rpm | 2.40 |
| fuel_cost | 342.97 |
| variable_cost | 120.00 |
| fixed_cost | 300.00 |
| dispatch_fee | 120.00 |
| net_profit | 317.03 |
| true_net_cpm | 0.53 (0.5284) |
| break_even_rate | 847.75 |
| counter_offer_rate | 1347.75 |
| verdict | "negotiate" (1347.75 ≤ 1440) |

This is the demo headline: **"$2.40 a mile on paper. $0.53 in your pocket."**

## Geography (geo.py)
- Distance = haversine miles × **1.2** (road circuity). State this in the pitch; it's an estimate.
- Drive time = miles / **50 mph**.
- City → lat/lng: look up `data/cities.json` first. On miss, call Nominatim
  (`https://nominatim.openstreetmap.org/search?q=...&format=json&limit=1`, custom `User-Agent`,
  max 1 request/sec) and write the result back to the cache. **Pre-warm every demo city Saturday.**
- If a city has no state, return a warning; don't guess.
- `distance_miles` and the haversine math are pure. `resolve()` is the ONE function in geo.py that
  touches the cache file and the network; the fetcher is injectable so tests never hit the network.

## Chain optimizer (optimizer.py)
Input: profile, starting place + time, candidate loads (pasted offers + simulated board, filtered by trailer type).
Search: depth-first, chains of length 1–3.

Rules for adding load L after current position P at time T:
1. Deadhead P → L.origin ≤ **250 mi**.
2. Arrival = T + drive time (+ rest). Must be ≤ `pickup_window_end`. If early, wait until `pickup_window_start`.
3. Loading and unloading take **2 h each**.
4. Delivery arrival must be ≤ `delivery_by` (arrival is checked; unloading happens after).
5. Simplified hours-of-service: max **11 h driving** before a **10 h rest**. Track driving hours since
   last rest; insert a rest whenever the next drive would exceed 11. A single drive longer than the hours
   left is **split mid-drive**: drive until 11 h, rest 10 h, continue. Waiting ≥ 10 h (e.g. overnight for a
   pickup window) counts as a rest and resets the clock. Loading/unloading do not reset it.
   (Say "simplified HOS" to judges. Real rules also include the 14-hour window and 30-min break; not modeled.)
6. No load used twice.

Score each chain: `total_net_profit` = sum of leg net profits − cost of deadhead home
(home deadhead costed with empty mpg + variable + fixed per mile).
Return the top 3 by `total_net_profit`, plus `net_per_day`.
Every returned run includes `days` and `net_per_day` (ranking stays by `total_net_profit`).

**Losing runs fill leftover slots.** Profitable runs are chosen first (with the 150-mi rule and its fallback
above). If fewer than 3 were found, runs with `total_net_profit ≤ 0` that still end ≤ 150 mi from home fill
the remaining slots (smallest loss first, still one per first load), with `losing: true` and a
`losing_reason` naming the biggest cause: empty miles to pickup, empty miles overall (≥ 25% of the run),
or low pay per loaded mile. Losing runs never outrank a profitable one. An empty list means nothing
feasible ends near home. Exclude chains that end more than
**150 mi from home** unless nothing else exists; if so, add a note.

60 loads, depth 3, with the 250-mi prune runs in well under a second. Don't optimize further.

## Gemini (gemini.py)
### Extract — `extract_load(text: str | None, image_bytes: bytes | None) -> ExtractionResult`
- Same function, same response schema for text and screenshots (Gemini accepts image parts).
- Use structured output (`response_mime_type="application/json"` + `response_schema`).
- Prompt must say: return `null` for anything not present; never invent; if the rate could be
  per-mile vs total, return the total if computable and add a warning; always "City, ST".
- After Gemini returns, **code** validates: rate > 0; if `rate < 20` it's probably per-mile →
  multiply by loaded miles and warn; missing state → warning; mark low-confidence fields.
- Keep 5 real load texts from Dad + 2 screenshots in `backend/tests/fixtures/`. Test against them.

### Explain — `explain(economics, chain, cashflow) -> str`
- Input: JSON of already-computed numbers only. Output: ≤ 3 sentences, plain English, driver voice.
- Prompt: "Use only numbers present in the input. Do not compute anything new."
- Code check after: every `$` or number in the output must appear in the input (string match after
  rounding). If not, fall back to a template sentence. This is what backs up "the AI never gets a
  number wrong."

## Capital One Nessie (nessie.py + scripts/seed_nessie.py)
**Check the Capital One challenge statement on Discord/at the booth first.** It was still "TBD" on Devpost.
If their prompt differs, change the framing, not the architecture.

### Seed (run once, Friday night)
`scripts/seed_nessie.py` creates: customer "Dad's LLC" → Checking account (balance ~$3,800) →
merchants (Pilot/Love's-style fuel stops with `geocode`, a tire shop, a repair shop, a toll authority,
an insurer) → 90 days of purchases (diesel, tires, repairs, tolls) → recurring bills (truck payment
$2,150 due on the 1st, insurance $1,100 due on the 5th, phone/ELD $65) → deposits (past load payments,
each with a broker name in `description`). Save created IDs to `backend/data/nessie_ids.json`.
If Nessie is down or returns errors, `nessie.py` reads `backend/data/nessie_fixture.json`
(same shapes, recorded from a successful run). **Record that fixture as soon as seeding works.**

### Feature 1: "Costs from your bank" → `GET /api/costs/from-bank`
From the last 90 days of purchases, grouped by merchant category:
```
fuel_spend_90d        -> fuel_price = fuel_spend / gallons (gallons parsed from description "DIESEL 112.4 GAL")
maintenance_90d       -> variable_cpm = (maintenance + tires + tolls) / miles_90d
fixed_monthly         = sum of recurring bill amounts
miles_90d             = profile.miles_per_month * 3   (bank data has no miles; say so)
```
Returns a proposed `TruckProfile` patch with a side-by-side "you entered vs. your bank says".
The driver clicks Accept. Demo moment: "He guessed $0.15/mi for maintenance. His bank says $0.27."

### Feature 2: "Can I afford this run?" → `POST /api/cashflow`
Split of work: `nessie.py` exposes `get_checking_balance() -> float` and
`get_upcoming_bills(days: int) -> list[dict]` (each `{payee, amount, due_date}`), normalized so
nothing downstream sees raw Nessie JSON. `cashflow.py` is pure and does the simulation below.
Input: chain + today's date. Simulate day by day:
- Start = current checking balance.
- Subtract fuel cost on each leg's pickup day (diesel is paid up front).
- Subtract bills on their due dates.
- Add each load's pay on `delivery date + payment_terms_days`. Pay deposited = `rate − dispatch fee`
  (the dispatcher takes his cut before the driver sees it).
- Report lowest balance and date. If negative, re-run with quick pay
  (paid 2 days after delivery, minus `rate × quick_pay_fee_pct`) on the fewest loads needed (earliest delivery
  first) and report whether that fixes it and what it costs. `timeline` is the ORIGINAL run (it shows the dip);
  the quick-pay result is reported in `quick_pay_fixes_it` / `quick_pay_cost`.
- Timeline details: the first entry is `{date: today, label: "Checking balance today", amount: 0, balance}`;
  money out is booked before money in on the same day; bills count only if due between today and the run's
  last payment. If quick pay can't fix it, `quick_pay_cost` is the cost of quick pay on every load.
Demo moment: "Best run makes $1,940, but your balance goes to −$312 on Oct 1 when the truck payment
hits. Quick pay on the Richmond load costs $36 and keeps you positive."

## Module interfaces (frozen: everyone codes against these signatures)
```python
# geo.py
def resolve(place: Place) -> tuple[Place, list[str]]            # fills lat/lng, returns warnings
def distance_miles(a: Place, b: Place) -> float                 # haversine * 1.2
# profit.py
def evaluate_load(load: Load, profile: TruckProfile, deadhead_miles: float, loaded_miles: float) -> LoadEconomics
# optimizer.py
def best_chains(profile: TruckProfile, start: Place, start_time: datetime, loads: list[Load], top_k: int = 3) -> list[Chain]
# cashflow.py
def simulate(chain: Chain, loads_by_id: dict[str, Load], start_balance: float, bills: list[dict], today: date) -> CashflowCheck
# gemini.py
def extract_load(text: str | None, image_bytes: bytes | None, mime_type: str | None) -> ExtractionResult
def explain(payload: dict) -> str
def counter_message(economics: LoadEconomics, broker: str | None) -> str
# nessie.py
def get_checking_balance() -> float
def get_upcoming_bills(days: int = 45) -> list[dict]             # [{payee, amount, due_date: date}]
def get_costs_from_bank(profile: TruckProfile) -> dict          # {current, proposed, evidence}
```
Until a module is done, its owner commits a **stub** with the exact signature that returns realistic fake data,
so `main.py` and the frontend can wire everything on day one.

## API (FastAPI)
| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/profile` | → `TruckProfile` |
| PUT | `/api/profile` | `TruckProfile` → `TruckProfile` (home/current_location may omit lat/lng: the backend resolves them; 422 if a city can't be placed) |
| POST | `/api/extract` | multipart: `text?` and/or `image?` → `ExtractionResult` |
| POST | `/api/evaluate` | `{load: Load}` → `LoadEconomics` (deadhead from `current_location`) |
| POST | `/api/offers` | `{loads: Load[]}` → `LoadEconomics[]` sorted best first |
| POST | `/api/chains` | `{seed_load_ids?: str[], include_board: bool}` → `Chain[]` (top 3) |
| GET | `/api/board` | → `Load[]` (simulated) |
| GET | `/api/costs/from-bank` | → `{current: TruckProfile, proposed: TruckProfile, evidence: dict}` |
| POST | `/api/cashflow` | `{chain: Chain}` → `CashflowCheck` |
| POST | `/api/explain` | `{economics, chain?, cashflow?}` → `{text: str}` |
| POST | `/api/counter-message` | `{economics}` → `{text: str}` (Gemini writes message; rate comes from code) |

| GET | `/api/health` | → `{modules: {profit, geo, optimizer, cashflow, gemini, nessie: "stub"\|"live"\|"fixture"}, demo_now, board_loads, pasted_loads}` |

Notes:
- **Demo clock.** The backend's "now" is `DEMO_NOW` from `.env` (default `2026-09-21T06:00`, matching the
  simulated board). `/api/chains` starts the truck at `current_location` at that time; `/api/cashflow`
  uses its date as `today`. Set `DEMO_NOW=` (empty) to use the real clock.
- **Pasted loads are remembered.** `/api/evaluate` and `/api/offers` keep every non-simulated load in memory
  by `id`. `/api/chains` looks `seed_load_ids` up there (404 if unknown) and adds them to the candidate pool
  alongside the board; they are candidates, not forced first legs. Memory resets when the server restarts.
- `/api/offers` sorts by `true_net_cpm`, highest first.
- Every backend module has `STATUS = "stub"`; set it to `"live"` when you replace your stub (nessie may report
  `"fixture"`). `/api/health` shows them.

Frontend must work against **mock JSON** for every route until Saturday 8 AM, so C is never blocked.
Put mocks in `frontend/src/mocks/`.

## Screens (frontend)
1. **Setup** — truck profile form + "Pull costs from my Capital One account" button → diff view → Accept.
2. **Check a load** — big paste box + drag-and-drop image. → Confirm card (editable fields, low-confidence
   fields highlighted yellow, warnings listed). → Result card: posted $/mi crossed out, true $/mi huge,
   cost waterfall (rate → dispatch → fuel → variable → fixed → net), verdict chip, counter-offer button.
3. **Plan my run** — map with numbered legs (solid = loaded, dashed = deadhead, home pin), top 3 chains as
   cards, "Can I afford this?" cash-flow line chart with bill markers, Gemini explanation at top.

## MVP vs stretch (in build order)
**MVP — must work in the demo by Saturday 6 PM feature freeze**
1. Profit math + golden tests
2. Paste text → extract → confirm → result card
3. Chains over simulated board + pasted offers, on the map
4. Nessie cost import (with fixture fallback)
5. Cash-flow check
6. Explanation with number check

**Stretch — only after all MVP items work end to end**
7. Screenshot input (same extractor; mostly a frontend drop zone) ← do this first among stretch; the team wants it
8. Counter-offer message
9. Real road polyline for the final chain (OSRM demo server) — skip if it fights you
10. Live diesel price by region (EIA weekly data)

## Things we will NOT build
Login, real load board integration, mobile app, real hours-of-service compliance, tolls by route,
broker credit scores, deployment beyond localhost (a Vultr deploy is optional Sunday-morning polish only).
