# Deploy

**One server.** `backend/app/main.py` serves `frontend/dist` when it exists, so the API and the site share
one URL and there is no CORS to configure.

```bash
cd frontend && npm run build          # writes frontend/dist
cd ../backend && source .venv/bin/activate
uvicorn app.main:app --port 8000      # http://localhost:8000 = the whole app
```

## Fastest public link (no accounts): Cloudflare quick tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```
It prints a `https://<random>.trycloudflare.com` URL that anyone can open. The laptop has to stay awake
and the URL changes each run, so paste the current one into Devpost right before submitting.

## Permanent link: Render (one service)
Render builds the frontend and runs the API from the same service (see `render.yaml`). Vercel is no longer
needed; the old two-service steps are below for reference.

---

# Reference: Render (backend) + Vercel (frontend) + the MLH/GoDaddy domain

Nihal does the sign-ins; everything else is in the repo. Total ~15 minutes, plus DNS time.
Config lives in `render.yaml` and `frontend/vercel.json`.

## 1. Backend on Render
1. render.com → **Sign in with GitHub** → allow the **VTHACKATHON** org (Ben may have to approve it).
2. **New → Blueprint** → pick `VTHACKATHON/VTHACKS` → it reads `render.yaml` → **Apply**.
3. On the new `loadcheck-api` service → **Environment** → add:
   - `NESSIE_API_KEY` = the key from our root `.env`
   - `GEMINI_API_KEY` = Ben's key (skip while Gemini is a stub)
   - `ALLOWED_ORIGINS` = leave empty for now; fill it in step 3
4. Wait for the first deploy, then open `https://<service>.onrender.com/api/health`.
   It must show `"nessie":"live"`. If it says `fixture`, the key is missing or wrong.

**Free plan:** the service sleeps after ~15 min idle and takes 30–60 s to wake. Open the site once
before judging. `DEMO_NOW` is already set, so the demo clock matches the simulated board.

## 2. Frontend on Vercel
1. vercel.com → **Sign in with GitHub** → **Add New → Project** → import `VTHACKATHON/VTHACKS`.
2. **Root Directory: `frontend`** (important). Framework auto-detects Vite; `vercel.json` covers the rest.
3. **Environment Variables** → `VITE_API_BASE_URL` = the Render URL (no trailing slash),
   e.g. `https://loadcheck-api.onrender.com`.
4. **Deploy**, then open the `*.vercel.app` URL and click through the demo.

## 3. Let the backend accept the site
Back on Render → `ALLOWED_ORIGINS` = your Vercel URL **and** the custom domain, comma-separated:
`https://loadcheck.vercel.app,https://loadcheck.tech` → save (it redeploys).
Preview builds (`*.vercel.app`) are already allowed by a regex in `main.py`.

## 4. Free domain (MLH × GoDaddy)
1. Claim it from the hackathon's GoDaddy/MLH link. Short, no hyphens, e.g. `loadcheck.tech`.
2. Vercel → project → **Settings → Domains** → add it. Vercel shows the exact records.
3. In GoDaddy DNS, add what Vercel asks for (usually `A @ 76.76.21.21` and `CNAME www → cname.vercel-dns.com`).
4. DNS can take 10 minutes to a few hours. Add the domain to `ALLOWED_ORIGINS` (step 3) as soon as it's live.

## 5. After it's up
- Open `https://<domain>` on a phone and run the story once.
- Take the advance, then hit **Reset demo** so the bank sandbox is clean for judging.
- Devpost "Try it out" link = the domain. Keep the local setup as the backup demo.

## If something breaks
| Symptom | Cause |
|---|---|
| Frontend loads, every call fails | `VITE_API_BASE_URL` wrong, or the domain isn't in `ALLOWED_ORIGINS` |
| `"nessie":"fixture"` in `/api/health` | `NESSIE_API_KEY` missing/typo'd on Render |
| First load hangs ~40 s | Free plan cold start; open it once before judging |
| Map is grey | Tile server unreachable (offline-tiles work is in `docs/FRONTEND_NOTES.md`) |
| Numbers differ from the laptop | Render is on the live Nessie account; run **Reset demo** if a rehearsal left an advance |
