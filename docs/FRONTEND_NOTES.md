# Frontend notes (Sat Sep 19, evening)

For the frontend teammate. Ordered: **1–3 are what we actually need before the demo.** Everything below that is
nice-to-have. Ask before touching backend files; `frontend/` is yours.

**Pull `main` first.** A lot landed today (PRs #17–#22). Run `npm ci && npm run build`, and keep
`frontend/src/types.ts` mirroring `backend/app/models.py`.

---

## 1. Offline map tiles (still open, highest risk)
Map tiles come from OpenStreetMap over the internet. **With the venue Wi-Fi down, the map is blank grey**, and the map
is the centerpiece of the Capital One pitch (green → red → green).

Pick whichever is fastest:
- **Cache tiles**: pre-download the ~6 zoom levels around VA/NC/GA/TN/MD we use and serve them locally, or
- **No-tile fallback**: if a tile fails to load, hide the tile layer and draw the route on a plain background with the
  city pins (the colored lines and markers already carry the story), plus a small "offline map" note.

Test with Wi-Fi off, in a fresh profile (no browser cache).

## 2. Phone layout
Judges may open the deployed link on a phone. Check every screen at 390 px wide: the map card, the cash-flow chart,
the run timeline, the tables (they should scroll sideways, not squash), and the Capital One advance card.

## 3. The advance card is the money shot — make it land
`src/components/AdvanceOffer.tsx` (red state → confirm → green state). Ideas, in order:
- Make the green "done" state louder: a Capital One-ish accent, a ✓, and the deposit id in a monospace chip.
- Animate the repaint: when the route flips red → green, a short pulse on the route or a "+$1,044" chip rising from
  the Atlanta pin sells it better than an instant swap.
- Keep the confirm card inline (never `window.confirm`) — that's a hard rule, it blocks the browser automation.

---

## 4. Coming from the backend: AI follow-up questions (I'm building the API now)
After a load is evaluated, the app asks 1–3 short questions about what the offer didn't say (lumper/detention fees,
extra empty miles, damage), then re-runs the numbers. Contract (will be in SPEC.md before it merges):

```
POST /api/followups  {load, economics}  -> {questions: [{id, question, kind: "money"|"miles"|"text", hint}]}
POST /api/adjust     {load, answers: {id: value}} -> {economics: LoadEconomics, applied: [{label, amount|miles}]}
```
UI: a card under the verdict, "A few more questions", one input per question, then **Update my verdict →**. Show the
before/after ("$0.55/mi → $0.49/mi · verdict negotiate"). If you have time and want it, take the UI — tell me and I'll
stop at the API.

## 5. Smaller polish
- **Map card**: add the pitch line under the legend, e.g. *"Capital One already knows his bills. LoadCheck puts them on
  his map."*
- **Cash-flow chart**: the trip is only 3 days now; consider dots + day labels instead of a long line.
- **"Try an example"**: on a slow machine the textarea fills a beat later; disable **Read my offer** until the text is in
  (it already is), maybe flash the textarea so the demo driver knows it worked.
- **Setup**: the new **"How you get paid"** switch (broker net-30 vs dispatcher weekly) and **"My rule: minimum posted
  ($/mi)"** could use a one-line explanation of why they matter.
- **`?dev` strip**: `nessie` shows `fixture` until the first bank call, even when live. Backend fix pending; don't chase it.

## 6. Don't break these (the demo depends on them)
- "Try an example" must stay the Greensboro → Jacksonville bad load.
- Reset demo calls `POST /api/demo/reset-bank` **and** restores the profile; keep both.
- "Accept bank costs" needs its two-step confirm (it changes every number in the story).
- Money numbers come from the backend (`advance_offer`, `economics`, `cashflow`). Don't compute money in the UI.
