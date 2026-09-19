# LoadCheck frontend

Teammate 4's three-screen React app. All backend calls go through `src/api.ts`; backend contracts are unchanged.

## Run

Use Node.js 22.18+ (Node 24 recommended), then:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Start the API separately from `backend/` with `uvicorn app.main:app --reload`. Live API mode is the default. No API keys belong in frontend environment variables.

For the standalone fixture demo, copy `.env.example` to `.env` and set `VITE_USE_MOCKS=true`, then restart Vite. `VITE_API_BASE_URL` defaults to `http://localhost:8000`. Never silently fall back to mocks on API failure.

```sh
npm run build
npm run preview -- --port 5173
```

The native Vite config loader requires the Node version above. In a restricted Windows environment where the development dependency scanner cannot read parent directories, use the production build/preview commands instead.

## Demo in five steps

1. **Check a load:** click **Try an example**, then **Read my offer**. Inspect the warnings and yellow low-confidence fields. Every extracted field, including location coordinates, can be edited. Calculation requires the confirmation button.
2. **Calculate what I keep:** see posted versus net rate, cost split, verdict, counter target, and explanation. Generate and copy the broker message. Read another offer, then rank the confirmed offers.
3. **Plan my run:** optionally include the clearly labeled simulated board. Select a returned chain to fit the map. Solid lines carry loads; dashed lines are empty legs; purple dashes return home. Numbered P/D pins identify pickups and deliveries.
4. **Can I afford this run?:** inspect the original balance timeline, zero line, red bill markers, event table, lowest balance and quick-pay guidance.
5. **Setup:** save truck costs, pull Nessie sandbox costs, inspect the side-by-side differences, then accept or keep the saved profile. **Reset demo** restores the supplied profile and clears local offers/results.

## Implementation and limitations

- React + TypeScript + Vite provide the app; Tailwind is wired through the Vite plugin. Leaflet/react-leaflet provide map interaction and OpenStreetMap tiles; Recharts renders cash flow. These are the dependencies required by the teammate assignment.
- `src/types.ts` mirrors every model/request/response in `backend/app/models.py`. Dates travel as ISO strings. Arbitrary dictionary fields remain dictionaries.
- `src/mocks/` contains the board/profile fixtures and a response for every route. The fixed economics reproduce the golden example. Mock extraction does **not** parse arbitrary input, and mock routes/cash flow are illustrative; the UI labels this.
- The backend's profit, geo, optimizer and cash-flow modules are live; Gemini (extraction/explanations) and Nessie (bank data) are still stubs until those teammates merge. The UI shows each module's status from `/api/health`. It displays up to three chains, including losing runs (flagged with their `losing_reason`).
- Editing a city clears old coordinates, preventing a new city from retaining a previous city's map position. Missing coordinates produce a map notice rather than invented locations. Map tiles need internet access.
- Changing saved costs invalidates old results. Bank import requires saving profile edits first. Reset does not erase the backend's in-memory offer registry because the frozen API exposes no delete/reset endpoint; planning only submits currently selected local IDs.
- All economics and decision values come from API responses (or explicitly labeled fixtures). The frontend only formats numbers and calculates display differences/proportions.
- Screenshots accept PNG/JPEG/WebP up to 10 MB and are sent as multipart form data. Backend image parsing becomes real when the Gemini teammate implements it.

## Verification

Backend: `cd backend && pytest -q` — 56 passed, including the golden profit test (±$0.01). `python scripts/demo_check.py --in-process` — 15/15.

Frontend: `npm run build` (TypeScript + Vite) passes. Verified in the browser against the live API with mock mode off: example → confirm → economics, chain planning + map, cash-flow chart and table, and the bank comparison.

Judge explanation: “The frontend asks the API to read the offer, makes the driver confirm every field, and displays the code's economics. It compares runs on a map and shows when bank bills hit. Gemini writes words; backend code supplies the numbers.”
