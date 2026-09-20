# Start the next session

Open a fresh Claude Code session in `~/Documents/CS/VTHACKS` and paste the block below.

```
We're finishing LoadCheck for VTHacks 14 (submit Sun 7:15 AM ET). Repo: ~/Documents/CS/VTHACKS
(GitHub: VTHACKATHON/VTHACKS). I'm Nihal; you're my lead engineer. I steer, you write code, and I have to be able
to explain everything to judges.

First: git checkout main && git pull, then read docs/STATUS.md and docs/RUNBOOK.md. Don't re-ask anything the
"Decisions already made" section answers. Confirm main is green: pytest -q (105), python scripts/demo_check.py
--in-process (15/15), npm run build.

What LoadCheck is: an owner-operator pastes a load offer; we show what he'd actually keep per mile after empty
miles, diesel and fixed costs; we find a better 2-3 load run that ends at home; and we put his Capital One (Nessie)
bank account on the map, so he sees where on the road he runs out of money and can take a Capital One advance that
fixes it. Capital One is the prize we're going for.

Priorities, in order:
1. Gemini PR #20 (Ben's). My fixes are already pushed to his branch. Get GEMINI_API_KEY into .env, test a real
   pasted offer end to end, set gemini.STATUS = "live", then merge. Until this lands, anything a judge pastes
   returns a canned Roanoke->Charlotte load.
2. Help me rehearse: 4 minutes, timed. Bad load -> better run -> map red in Tennessee -> Capital One advance ->
   green. Tell me what to say and where I'm slow.
3. Devpost draft: title, one-line pitch, the story, tags (Capital One, Gemini). No live link; we demo locally.
4. Only if time remains: Feature C (receipt photo -> Gemini reads it -> Nessie purchase -> real spending profile,
   issue #15, designed in docs/CAPITAL_ONE_FEATURES.md).

House rules: SPEC.md first for any model or route change; numbers come from code, never from Gemini; cashflow.py
stays pure; only nessie.py talks to the bank; every new function gets a pytest; one branch per feature; ask before
every git push; stop after each feature with test output and a 5-line summary I can say out loud. You can't merge
PRs yourself (auto mode blocks it) — hand me the command.

Demo gotchas: wait for "Try an example" to fill the textarea before clicking Read my offer; click "Reset demo" before
pitching so no rehearsal advance is left in the bank; don't accept bank costs mid-pitch (two-step confirm now, but
it still changes every number); give the first page load a couple of seconds before clicking (the map paint is heavy).
```

## Quick facts
- Story numbers: bad load $2.43 -> **$0.55/mi** (net $326, below his $3.00/mi rule); best run L027->L058->L012
  **$1,496** in 2.6 days ending at home; start **$2,500**, truck payment **Sep 22 in Tennessee** -> **-$313**,
  low **-$494**; Capital One advance on L027 **+$1,044**, fee **$36**, repaid Oct 21 -> all green.
- Run it: `cd frontend && npm run build` then `cd ../backend && source .venv/bin/activate &&
  uvicorn app.main:app --port 8000` -> http://localhost:8000 (or two dev servers: `npm run dev` + `--reload`).
- Checks: `pytest -q` (105) · `python scripts/demo_check.py --in-process` (15/15) · `npm run build`.
