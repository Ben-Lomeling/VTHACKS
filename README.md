# LoadCheck — VTHacks 14

**$2.40 a mile on paper. $0.53 in your pocket.**

Owner-operator truck drivers get load offers as texts, emails and screenshots. LoadCheck reads the offer
(Gemini), makes the driver confirm it, and then **code** computes what he actually keeps after the empty
drive to pickup, fuel, maintenance, the truck payment and the dispatcher's cut. It finds a better 2–3 load
run that ends near home, checks the run against his real bank balance and bills (Capital One Nessie),
and suggests a counter-offer when a load is close.

> The AI reads the offer and explains the answer. Code does all the math, and we check every number the
> AI says against the math.

What's simulated: the 60-load board (`backend/data/seed_loads.json`, labeled "Simulated" in the UI) and the
Nessie bank data (sandbox data we seeded). Road miles are straight-line × 1.2; hours-of-service rules are
simplified. See `SPEC.md` for the full contract.

---

## Teammates: start here

### 1. One-time setup (10 min)
```bash
git clone https://github.com/Ben-Lomeling/VTHACKS.git
cd VTHACKS
cp .env.example .env                  # put your API key in .env; never commit it

cd backend
python3 -m venv .venv                 # needs Python 3.11 or newer: python3 --version
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                             # should be all green
uvicorn app.main:app --reload         # API on http://localhost:8000  (docs: /docs)
```
Check that it's up: http://localhost:8000/api/health lists every module as `stub` or `live`.

### 2. Find your job
| Who | You own (only touch these) | Branch prefix | Paste this into Codex |
|---|---|---|---|
| Nischal (lead) | `backend/app/models.py main.py profit.py geo.py optimizer.py cashflow.py`, their tests, `data/profile.json`, `data/cities.json`, `requirements.txt`, `README.md`, `SPEC.md` | `engine/` | `prompts/1_NISCHAL_engine_fable.md` |
| Gemini teammate | `backend/app/gemini.py`, `backend/tests/test_gemini_*.py`, `backend/tests/fixtures/`, `scripts/eval_extraction.py` | `gemini/` | `prompts/2_TEAMMATE_gemini_codex.md` |
| Nessie teammate | `backend/app/nessie.py`, `scripts/seed_nessie.py`, `scripts/record_fixture.py`, `backend/data/nessie_*.json`, `backend/tests/test_nessie*.py` | `nessie/` | `prompts/3_TEAMMATE_nessie_codex.md` |
| Frontend teammate | everything in `frontend/` | `frontend/` | `prompts/4_TEAMMATE_frontend_codex.md` |

Your module already exists as a **stub** with the exact function signatures and fake data, so the API and
frontend work today. Replace the inside of your functions; **never change a signature, model or route**.
When your module is real, set `STATUS = "live"` at the top of your file.

### 3. How to use Codex
1. Open the repo in Codex. It reads `AGENTS.md` automatically; that holds the rules.
2. Paste your prompt from `prompts/`, then give it **one task at a time** ("Do Task 1 only").
3. Before you accept anything: read the diff, run `pytest -q`, and make sure you can explain it out
   loud in 30 seconds. Judges will ask. "Codex wrote it" costs us points.

### 4. Every task, every time
```bash
git checkout main && git pull                     # always start from fresh main
git checkout -b gemini/extract-validation         # <your prefix>/<short-task-name>
# ... work, then:
cd backend && pytest -q                           # must be green
git add -A && git commit -m "gemini: validate per-mile rates"
git push -u origin gemini/extract-validation
```
Then open a Pull Request on GitHub into `main`, fill in the template (paste your `pytest -q` output),
and ping Nischal in the group chat. Nischal merges. Keep PRs small, and merge at least every 3 hours.

### 5. Rules that keep us from breaking each other
- Only edit files you own (table above). Need a model, route or signature changed? Ask Nischal; he changes
  `SPEC.md` first and tells everyone.
- Never commit `.env`, API keys, or Dad's unredacted texts (strip names, phone numbers, MC numbers).
- Tests never call the network (Gemini/Nessie tests use fixtures or fakes). CI runs `pytest` on every PR.
- Code does all math. Gemini never produces a number we display.
- The backend clock is `DEMO_NOW` in `.env` (default `2026-09-21T06:00`), so the simulated board's
  dates line up. Don't "fix" dates in the data.

### Checkpoints (from the game plan)
- **Sat 12 PM:** paste → confirm → result works end to end on the real backend.
- **Sat 4 PM:** every MVP feature on real data.
- **Sat 6 PM:** feature freeze. Bug fixes only after this.
- **Sun 7:15 AM:** submit on Devpost.

---

## API (running at http://localhost:8000)
| Method | Path | Purpose |
|---|---|---|
| GET/PUT | `/api/profile` | Driver's truck + cost profile |
| POST | `/api/extract` | multipart `text` and/or `image` → extracted load + confidence + warnings |
| POST | `/api/evaluate` | one load → true economics + verdict |
| POST | `/api/offers` | several loads → ranked economics |
| POST | `/api/chains` | best 2–3 load runs that end near home |
| GET | `/api/board` | the simulated load board |
| GET | `/api/costs/from-bank` | costs derived from Capital One Nessie |
| POST | `/api/cashflow` | "can I afford this run?" balance simulation |
| POST | `/api/explain` | plain-English explanation (numbers checked) |
| POST | `/api/counter-message` | message to the broker with the counter rate |
| GET | `/api/health` | which modules are live vs stub |

Interactive docs: http://localhost:8000/docs

## Repo layout
```
SPEC.md        the contract: models, formulas, routes, interfaces
AGENTS.md      rules for Codex (and humans)
prompts/       one kickoff prompt per teammate
backend/app/   FastAPI app + modules
backend/data/  seed loads (simulated), profile, city cache, Nessie fixture
backend/tests/ pytest; golden profit test must stay green
scripts/       Nessie seed script, demo checks
frontend/      React + Vite + TS (frontend teammate)
```
