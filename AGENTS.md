# AGENTS.md — instructions for Codex (and humans)

Read `SPEC.md` before writing any code. It is the contract.

## Rules
- Do not change a Pydantic model, TS type, or API route unless the task explicitly says to
  update SPEC.md too. Other people are coding against them right now.
- `profit.py`, `optimizer.py`, `cashflow.py` are pure functions: no network, no file I/O, no Gemini.
  In `geo.py` the math is pure; only `resolve()` touches `data/cities.json` and Nominatim.
- When you replace your module's stub, set `STATUS = "live"` at the top of it (shows in `/api/health`).
- Tests never hit the network. Run them from `backend/`: `pytest -q`. CI runs them on every PR.
- Gemini output is never shown as a number. Numbers come from `profit.py` / `optimizer.py` / `nessie.py`.
- Every new backend function gets a pytest. Run `pytest -q` before saying a task is done.
  The golden test in SPEC.md must stay green.
- Keep functions small and typed. No new dependencies without saying why.
- Secrets only from `.env` (`GEMINI_API_KEY`, `NESSIE_API_KEY`). Never commit `.env`.
- Frontend: call the API through `frontend/src/api.ts` only. Until the backend route exists,
  return data from `frontend/src/mocks/`.

## Task sizing
Give Codex one small task at a time, e.g. "Implement `evaluate_load` in profit.py per SPEC.md
and make tests/test_profit.py pass." Review the diff before merging. Every teammate must be able
to explain their code to a judge; if you can't explain it, don't merge it.

## GitHub workflow
- One repo, **public** (Devpost requires it). Nischal owns `main` and merges every PR.
- Protect `main` in Settings → Branches: require a pull request before merging.
- Branch names by owner: `engine/...` (Nischal), `gemini/...`, `nessie/...`, `frontend/...`.
- One PR per task, small. PR description = what changed + test output. Codex cloud tasks open PRs
  directly; review them like any teammate's PR.
- Each person only touches files they own (see SPEC.md repo layout). That's what keeps merge
  conflicts near zero. `models.py` and SPEC.md change only through Nischal.
- Pull `main` before starting every task. Merge at least every 3 hours.
- Never commit `.env`, API keys, or Dad's unredacted texts.
