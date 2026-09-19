# Prompt 4 — Teammate (Codex): React frontend

Paste everything below the line into Codex. You can start immediately; you don't need the backend yet.

---

## Before you start (setup done by Nischal — read once)
- Follow **README.md → "Teammates: start here"** for setup, the branch flow and the PR template.
- Your code lives in `frontend/ (does not exist yet — create it with Vite)`. For backend modules a **stub** already exists with the frozen signatures
  (all routes in SPEC.md's API table) returning fake data. Replace the insides; keep every signature, model and route exactly.
- When your module is real, set `STATUS = "live"` at the top of the file (it shows in `GET /api/health`).
- The backend already runs with stub data: `cd backend && uvicorn app.main:app --reload` → http://localhost:8000/docs. Copy real response shapes from there into your mocks. CORS allows http://localhost:5173.
- The backend clock is `DEMO_NOW` in `.env` (default `2026-09-21T06:00`) so the simulated board's dates line up.
- Branch: `frontend/<short-task>`, one small PR per task into `main`, paste `pytest -q` output in the PR. Nischal merges.

You are working on **LoadCheck**, a hackathon project. Read `SPEC.md` and `AGENTS.md` first,
especially "Data models", "API", and "Screens". You own everything in `frontend/`. Do not change
backend code or the API shapes; if a shape is inconvenient, tell Nischal.

Stack: React + Vite + TypeScript, Tailwind, `react-leaflet` with OpenStreetMap tiles, `recharts`
for charts. The user is a truck driver: big text, high contrast, obvious buttons, works on a laptop
at the demo table. It will be judged for UI/UX, so it should look clean and deliberate, not like a template.

## Task 1 — foundation (tonight)
- `src/types.ts`: TypeScript types mirroring every Pydantic model in SPEC.md exactly.
- `src/api.ts`: one function per route. A flag `USE_MOCKS` (env var) returns data from `src/mocks/`
  instead of calling `http://localhost:8000`. Write realistic mocks for every route, using the golden
  example from SPEC.md ($1,200, 500 loaded mi, 100 deadhead → $2.40 posted, $0.53 true, counter $1,347.75)
  and cities from `backend/data/seed_loads.json`.
- App shell with 3 steps: **Setup**, **Check a load**, **Plan my run**.

## Task 2 — Check a load (the most important screen; the demo opens here)
- Large paste box plus a drag-and-drop / click-to-upload area for screenshots (send as multipart to `/api/extract`).
- **Confirm card:** every extracted field is editable. Fields with `confidence: "low"` are highlighted
  yellow; `warnings` show above the fields. The "Calculate" button is the only way forward.
- **Result card:**
  - Posted rate per mile shown struck through, and true net per mile shown very large beside it.
    This is the headline of the whole demo; make it hit.
  - A waterfall or stacked bar: rate → dispatcher → fuel → maintenance → fixed → what you keep.
  - Verdict chip: Take (green) / Negotiate (amber) / Skip (red).
  - "Counter at $X" plus a "Write the message" button (`/api/counter-message`) with copy-to-clipboard.
  - The Gemini explanation (`/api/explain`) in a quote-style box.
- Let the user add multiple offers and see them ranked (`/api/offers`).

## Task 3 — Plan my run
- Map: home pin, current location pin, numbered loads. Loaded legs are solid lines; empty (deadhead)
  legs are dashed; the drive home is dashed in a different color. Fit bounds to the chain.
- Top 3 chains as cards: total net, $/day, days, ends X miles from home, `feasible_notes` as small chips
  (e.g. "10-h rest before L022"). Clicking a card redraws the map.
- A "Simulated load board" badge must be visible whenever board loads are shown.
- **"Can I afford this run?"** button → `/api/cashflow` → line chart of balance over time, a red zero
  line, bill markers, and a clear sentence: lowest balance, date, and whether quick pay fixes it and for how much.

## Task 4 — Setup
Truck profile form (all `TruckProfile` fields, with units and short hints). A button
**"Pull my real costs from Capital One"** → `/api/costs/from-bank` → a side-by-side table
"You entered / Your bank says" with the difference highlighted, plus Accept / Keep mine.

## Task 5 — polish (Saturday afternoon, only after Tasks 1–4 work on the real backend)
Loading states for every call (Gemini takes a few seconds; show what it's doing), friendly error states,
an empty state per screen, and a demo-reset button that restores the profile. Test at 1280×800 and with
browser zoom at 125% for the projector.

## Done means
All three screens work with `USE_MOCKS=false` against the real backend, nothing in the console is red,
and you can drive the full demo script from the team doc without touching the keyboard except to paste.
Push to `frontend/...` and ask Nischal to merge.
