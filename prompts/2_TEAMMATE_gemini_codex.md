# Prompt 2 — Teammate (Codex): Gemini extraction + explanations

Paste everything below the line into Codex after pulling the repo (wait until Nischal says the
Phase 0 scaffold with stubs is pushed).

---

## Before you start (setup done by Nischal — read once)
- Follow **README.md → "Teammates: start here"** for setup, the branch flow and the PR template.
- Your code lives in `backend/app/gemini.py`. For backend modules a **stub** already exists with the frozen signatures
  (extract_load, explain, counter_message) returning fake data. Replace the insides; keep every signature, model and route exactly.
- When your module is real, set `STATUS = "live"` at the top of the file (it shows in `GET /api/health`).
- Put GEMINI_API_KEY in `.env` (repo root). Tests must use hand-made dicts/fakes, never the real API.
- The backend clock is `DEMO_NOW` in `.env` (default `2026-09-21T06:00`) so the simulated board's dates line up.
- Branch: `gemini/<short-task>`, one small PR per task into `main`, paste `pytest -q` output in the PR. Nischal merges.

You are working on **LoadCheck**, a hackathon project. Read `SPEC.md` and `AGENTS.md` first.
You own ONE file: `backend/app/gemini.py` (plus its tests and fixtures). Do not change any model,
route, or signature in SPEC.md's "Module interfaces"; other people depend on them. A stub of
`gemini.py` already exists; replace its internals, keep its signatures.

Use the `google-genai` Python SDK with the current Gemini Flash model. Key from `GEMINI_API_KEY`.

## Task 1 — `extract_load(text, image_bytes, mime_type) -> ExtractionResult`
- One function handles pasted text, a screenshot, or both, with one response schema.
- Use structured output (`response_mime_type="application/json"` + a response schema matching the
  `Load` fields). Prompt rules: return null for anything not present, never invent values, always
  format places as "City, ST", return the total rate when it can be computed.
- After Gemini returns, validate in plain Python (not in the prompt):
  - rate missing or ≤ 0 → warning + low confidence
  - rate < 20 → it's per-mile: if loaded miles are known, multiply and warn "Converted $X/mi to total";
    otherwise keep it, mark low confidence, and warn
  - city without a state → warning "State missing for Springfield"
  - pickup after delivery → warning
  - set `source` to "pasted" or "screenshot"; `id` = "P" + short uuid
- `confidence`: "low" for any field that was missing, converted, or warned about; else "high".
- If Gemini errors or times out (10 s), raise a clear exception; the route will show it.

## Task 2 — fixtures and tests
- `backend/tests/fixtures/loads/`: at least 8 text samples and 2 screenshots. Use the real ones from
  Nischal's dad (with names and phone numbers removed) plus ones you write that are deliberately
  messy: all caps, abbreviations ("RICH VA -> CLT NC", "2400 all in", "$2.10/mi", "PU 9/22 0800").
- `tests/test_gemini_validation.py`: test the Python validation with hand-made Gemini-style dicts.
  These tests must NOT call the API.
- `scripts/eval_extraction.py`: runs every fixture through the real API and prints a table of
  extracted fields and warnings. Target: every rate and city correct or flagged low-confidence.
  Run it and paste the output into the PR description.

## Task 3 — `explain(payload) -> str`
- Input: a dict of already-computed numbers (economics, optional chain, optional cashflow).
- Output: at most 3 sentences, plain English, like a straight-talking friend who knows trucking.
  Example tone: "Skip this one. It drops to 53 cents a mile after the empty drive. The Richmond run
  pays $640 more and gets you home Thursday."
- Prompt must say: use only numbers in the input; do not calculate anything.
- **Number check (required):** extract every number and dollar amount from the output; each must match
  a number in the input after rounding (to 0 or 2 decimals, or as cents: 0.53 ↔ "53 cents").
  If any don't match, discard the output and return a template sentence built in Python. Unit-test the
  checker with passing and failing examples.

## Task 4 — `counter_message(economics, broker) -> str`
A short, polite text to the broker asking for `counter_offer_rate` (rounded up to the nearest $25).
The rate is inserted by Python, not written by Gemini; Gemini only writes the wording around a
`{RATE}` placeholder. Same number check.

## Done means
Validation tests pass, the eval script output looks right, the stub is fully replaced, and you can
explain in 30 seconds to a judge how extraction works and why the AI can't put a wrong number on screen.
Push to a branch named `gemini/...` and ask Nischal to merge.
