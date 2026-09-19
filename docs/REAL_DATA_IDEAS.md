# Real data we could add (ideas, not started)

_Written Sat Sep 19, 2026. Nothing here is implemented. Checked that each source exists and how to get access;
re-read each one's terms before building._

## Why some data is simulated today
- **Load board:** DAT, Truckstop and 123Loadboard only give API access to approved, paying business partners
  (days to weeks). Convoy's open API shut down in 2023. So the board is simulated and labeled "Simulated" in the UI.
- **Bank:** Capital One Nessie is a sandbox on purpose. It's the sponsor's challenge API. Real bank data would
  mean connecting a real account (e.g. Plaid), which isn't something to demo on a projector.
- **Real already:** loads the driver actually gets offered, pasted in, and his own costs. Dad's data is the most
  valuable real data we have.

**Rule:** only our own keys. Never use someone else's API key or account, even if offered; it breaks the
provider's terms and can get the project disqualified.

## Candidates (ranked by impact per hour)

| # | Source | What it gives LoadCheck | Access | Effort |
|---|---|---|---|---|
| 1 | **EIA Open Data API**: weekly on-highway diesel prices | Real $/gal for the driver's region (Lower Atlantic = PADD 1C covers VA/NC/GA/FL), replacing the hard-coded $3.80 | Free key, register at eia.gov/opendata | ~1 h |
| 2 | **FMCSA QCMobile API** | "Is this broker legit?" Look up the broker's MC/docket number: active authority, bond/insurance, out-of-service status | Free WebKey; needs a Login.gov account | ~2 h (new feature) |
| 3 | **OpenRouteService**: directions (heavy vehicle profile) | Real truck road miles instead of straight-line × 1.2 | Free key, 2,500 req/day, 40,000/month | ~2–3 h |
| 4 | **USDA AMS MARS API**: Specialty Crops National Truck Rate Report (report 2375) | Real published spot rates per load for reefer produce lanes, to calibrate the simulated board's rates | Free MARS API key | ~2 h |

### How each would fit the architecture (when we build it)
- **Offline demo rule still applies:** every source gets a recorded fixture like Nessie's, and the app falls back
  to it on any error.
- **EIA** → used at profile load time to fill `fuel_price` (with `cost_source`-style labeling so the UI can
  say "EIA, week of …"). Pairs with Nessie's "your bank says $3.92".
- **FMCSA** → new `GET /api/broker/{mc}` + a badge on the confirm card. Needs a SPEC change (new route + model).
  Gemini would extract the MC number from the offer text.
- **OpenRouteService** → inside `geo.py` behind the same cache as `cities.json` (cache per city pair), so math
  stays pure and the demo works offline. Changes every number in the demo story, so re-tune the board after.
- **USDA** → a one-time script that pulls recent lane rates and rescales `seed_loads.json`; board stays
  `source: simulated` but its rates are grounded in published data. Only reefer produce lanes, so it's a
  calibration hint, not a full board.

### Recommendation
If there's time before a freeze: **#1 (EIA diesel)**. It's small, real, and easy to say to judges. **#2 (FMCSA)** is
the strongest new feature but needs a SPEC change. **#3 and #4** are post-hackathon.

## Sources
- EIA weekly diesel prices and regions: https://www.eia.gov/petroleum/gasdiesel/ · API: https://www.eia.gov/opendata/
- FMCSA QCMobile: https://mobile.fmcsa.dot.gov/QCDevsite/docs/getStarted · https://mobile.fmcsa.dot.gov/QCDevsite/docs/apiAccess
- OpenRouteService limits: https://openrouteservice.org/restrictions/ · services: https://openrouteservice.org/services/
- USDA truck rate report: https://mymarketnews.ams.usda.gov/viewReport/2375 · MARS API: https://marsapi.ams.usda.gov/services/v1.2/reports/2375
