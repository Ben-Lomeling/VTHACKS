# Start the next session

Paste the block below into a fresh Claude Code session opened in `~/Documents/CS/VTHACKS`. Fill in the Decision 1 line first.

```
We're continuing LoadCheck (VTHacks 14; submit Sun 7:15 AM ET). Repo: ~/Documents/CS/VTHACKS (GitHub: VTHACKATHON/VTHACKS).
First: git checkout main && git pull, then read docs/STATUS.md and docs/CAPITAL_ONE_FEATURES.md.
All PRs through #16 are merged; main should show 83 tests, demo_check 15/15, and npm run build passing. Confirm that first.

Capital One (Nessie) is our main prize. Their judges want a creative, meaningful use of Nessie, not an average banking
app. Our idea: turn a trucker's bank account into a map of the road ahead. Three features, in this order, so something
is demo-ready early:
A) Money on the map (issue #13), B) Get paid early: creates a Nessie deposit (#14), C) Receipt photos → Nessie purchases (#15).

Decision 1 (make the route go red on the road): <WRITE YOUR CHOICE, plus any changes to the idea since the doc was written>.
Update docs/CAPITAL_ONE_FEATURES.md with that decision before coding.

Then build Feature A. Follow AGENTS.md and SPEC.md: SPEC first for model/route changes, cashflow.py stays pure, only
nessie.py talks to Nessie, numbers never come from Gemini, every new function gets a test. Use a new branch per
feature, test in the browser against the live backend (backend: uvicorn app.main:app --reload; frontend: npm run dev),
and stop after each feature with test output + a 5-line summary I can explain to judges. Ask before every git push;
you may merge a PR once its CI is green and I've said OK. Keep docs/STATUS.md updated as you go.
```

## Quick facts for whoever picks this up
- Demo story today: bad load Greensboro → Jacksonville $2.43 → **$0.55/mi**; best run L027 → L058 → L012 **$1,496**,
  2.6 days; cash flow **−$359 on Oct 15**, quick pay fixes it for **$36**.
- With today's data the trip itself never goes red (the dip is Oct 5, after he's home). That's Decision 1.
- Don't click "Accept bank costs" mid-demo (changes every number); "Reset demo" restores the profile.
- Run everything: `cd backend && source .venv/bin/activate && pytest -q` · `cd .. && python scripts/demo_check.py --in-process` ·
  `cd frontend && npm run build`.
