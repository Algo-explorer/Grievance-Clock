# Deploy Grievance Clock: Vercel + Render + Atlas + Clerk

## What is ready

Repository: https://github.com/Algo-explorer/Grievance-Clock, branch `main`.

| Setting | Vercel frontend | Render backend |
|---|---|---|
| Root directory | `frontend` | `backend` |
| Framework/runtime | Next.js / Node.js 22 | Docker |
| Install command | `npm ci` | Dockerfile handles installation |
| Build command | `npm run build` | Dockerfile handles build and voice model downloads |
| Output directory | Next.js default (leave override off) | Not applicable |
| Start command | Managed by Vercel | Dockerfile starts Uvicorn using Render's `PORT` |
| Health check | `/` | `/api/health` |

CORS is already implemented. Browser requests use `/api` on the Vercel domain; Next.js proxies them to Render. This keeps Clerk session cookies, image previews and downloads on one origin. Do not replace frontend fetch/image URLs with the Render address. Direct API clients can use an allowed Origin and a Clerk Bearer token; cross-site cookie authentication is intentionally blocked. FastAPI independently verifies authentication on every private endpoint.

## 1. Collect your settings privately

Your local credentials have been separated into ignored `frontend/.env.local` and `backend/.env.local`. Open these locally and copy values into the platform dashboards; do not upload the files or paste secrets into GitHub. The `.env.example` files only show placeholders.

**Keep the current `DATA_ENCRYPTION_KEY` when connecting to your existing MongoDB database.** A new key cannot decrypt existing complaints or evidence. Back up the key separately from the database.

Clerk's publishable key, secret key and issuer must belong to the same Clerk instance. Development keys can be used for a staging demonstration subject to Clerk's development restrictions. For a public production launch, configure a production Clerk instance and its domain/DNS and use its live keys and actual Frontend API issuer URL. Enable your intended email/Google sign-in methods and complete the Clerk dashboard's production setup. Switching Clerk instances changes user identities; existing development accounts do not automatically become production accounts.

## 2. Reserve the frontend hostname

In Vercel, import the GitHub repository, set Root Directory to `frontend`, choose Next.js and Node.js 22.x. Choose your project name and note the final production hostname shown by Vercel, for example `https://grievance-clock-example.vercel.app`. Complete its first deployment after Render is live. If you need to create the project first with a placeholder `BACKEND_URL`, replace that value and redeploy in step 4; API requests cannot work against a placeholder.

Use the actual assigned hostname, not the example in this guide. A custom domain must also be added to Render's allowed origins and Clerk configuration.

## 3. Deploy Render

Create a **Web Service**, connect this repository, choose branch `main`, Root Directory `backend`, Language/Runtime **Docker**, Dockerfile path `./Dockerfile` and build context `.` (relative to the root directory). Leave Docker command overrides empty. Set health check path `/api/health`.

Alternatively use Render **New > Blueprint** with the root `render.yaml`; it sets the same backend configuration and prompts for secrets. The Blueprint selects a **paid Standard instance**, not the free tier. Review Render's current price before creating it. Local Whisper, Hindi Piper and OCR need more RAM than the 512 MB free instance; start with at least 2 GB, then measure your actual recording lengths/concurrency and increase memory if needed. The initial image build downloads large speech models and will take longer than later cached builds.

Add these backend environment variables:

| Name | Value |
|---|---|
| `APP_ENV` | `production` |
| `AUTH_MODE` | `clerk` |
| `COOKIE_SECURE` | `true` |
| `CLERK_ISSUER_URL` | Exact HTTPS Frontend API issuer of your selected Clerk instance, without a trailing slash |
| `ALLOWED_ORIGINS` | Exact Vercel HTTPS origin; comma-separate additional trusted custom domains, with no paths or trailing slashes |
| `MONGODB_URI` | Your existing Atlas connection string |
| `MONGODB_DATABASE` | `grievance_clock` |
| `DATA_ENCRYPTION_KEY` | Your existing Fernet encryption key |
| `AI_MODE` | `live` |
| `OPENAI_API_KEY` | Optional provider key; needed for cloud conversational understanding and other AI features |

Do not set `NEXT_PUBLIC_` database/provider secrets. Render does not need `CLERK_SECRET_KEY`. Leave `MODEL_DIR` and `DATA_DIR` at the Dockerfile defaults. Do not copy Windows model paths or local `DATA_DIR` into Render. The image installs Whisper small and the Hindi voice automatically; review [voice licensing](voice.md).

In Atlas **Network Access**, allow the outbound IP ranges shown for your Render service. In **Database Access**, ensure the database user has `readWrite` permission for `grievance_clock`. Do not confuse your Atlas dashboard login with the database username/password. If connectivity fails at startup, correct the Atlas allowlist and retry the deployment.

MongoDB stores encrypted cases and evidence, so a Render persistent disk is not required in this configuration. Speech models are included in the image. Keep one worker and one service instance: the current scheduler and rate limits are process-local. Reminders are checked while the service is running.

Deploy, wait for Live, and open `https://YOUR-SERVICE.onrender.com/api/health`. Confirm `ok: true`, `auth_mode: clerk`, `storage_backend: mongodb`, and local voice availability. An unauthenticated `/api/cases` request should return 401. Copy the Render service origin for Vercel.

## 4. Deploy Vercel

Add the following under Project Settings > Environment Variables, selecting Production (and only the Preview/Development environments you actually configure):

| Name | Value |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Publishable key from your chosen Clerk instance |
| `CLERK_SECRET_KEY` | Secret key from that same instance |
| `BACKEND_URL` | `https://YOUR-SERVICE.onrender.com`, with no `/api` path |
| `AUTH_MODE` | `clerk` |
| `APP_ENV` | `production` |

Build `main`. `frontend/vercel.json` supplies install/build commands. Do not set the root to the repository root, run Python on Vercel, or add a separate `NEXT_PUBLIC_BACKEND_URL`. Vercel needs no MongoDB URI or data encryption key.

`BACKEND_URL` is used when building the rewrite, so changing it requires a **redeploy**, not just saving the variable. Update Render's `ALLOWED_ORIGINS` if Vercel assigns a different hostname. Render restarts when environment values change. Preview deployments have different origins; add each intentionally trusted preview origin explicitly, or use a dedicated staging frontend/backend. Wildcard origins are rejected.

## 5. Verify before sharing

1. Open the Vercel domain and sign up/sign in with Clerk.
2. Open `/api/health` on the Vercel domain; it must reach the Render API.
3. Create a complaint, send text, upload multiple screenshots, and verify previews in chat and review.
4. Reload, sign out/in, and confirm saved complaints and attachments return.
5. Test microphone transcription on a short recording and Hindi read-aloud. HTTPS is required for browser microphone access; allow the browser permission.
6. Download the complaint/dossier; mark a test complaint resolved and delete only your test data when finished.
7. Use a second account and confirm it cannot see the first account's complaints.

Cloud AI requires working provider quota and the user's sharing consent. Merely setting a key does not establish available credit. Without a working provider, intake uses the labeled limited local parser; local Whisper and Hindi speech can still run.

## Troubleshooting

| Symptom | Check/action |
|---|---|
| Vercel build says `BACKEND_URL` missing | Add the HTTPS Render origin to the correct Vercel environment and redeploy. |
| API returns 502/504 or HTML | Check Render is Live, health URL is reachable, and the Vercel rewrite points to its actual origin. |
| Render startup MongoDB timeout | Atlas outbound-IP allowlist, database-user credentials and URI; redeploy after correcting them. |
| 401 after login | Match Clerk keys and issuer; ensure `ALLOWED_ORIGINS` contains the exact frontend origin used by the session. |
| 403 Origin not allowed | Correct Render `ALLOWED_ORIGINS`; include a custom domain or preview domain only if trusted. |
| Sign-in unavailable | Both frontend Clerk keys are needed; redeploy after setting them. |
| Existing cases fail to decrypt | Restore the original `DATA_ENCRYPTION_KEY`; do not create a replacement key. |
| Voice request times out | Try shorter recordings and inspect backend duration/memory. External Vercel rewrites have a proxy timeout; long CPU transcription may exceed it and would need a future background-job flow or direct authenticated upload. |
| Render exits during voice/OCR | Check memory usage and instance size; a successful build does not prove sufficient runtime memory. |
| Model download fails during Docker build | Inspect network/download errors and retry the build; models must be downloaded before runtime. |
| AI gives limited fallback replies | Check provider quota, model access and consent. This is separate from hosting/CORS. |

There are no wildcard CORS credentials. A successful preflight is not authentication. API paths bypass Next.js Clerk middleware (FastAPI verifies the token itself), avoiding the middleware body-size limit for evidence/audio uploads.

## Local development and containers

Install Python dependencies into the root `.venv` and run `npm ci --prefix frontend`. Configure the two service `.env.local` files, using `APP_ENV=development` and local origins for the backend. Run `npm run dev` from the repository root. Existing root config can be copied with `python -m scripts.split_local_env` without printing values.

For optional local containers: `docker compose --env-file frontend/.env.local up --build`. Compose uses the service-specific env files. Keep the existing encryption key and MongoDB settings. Docker was not available in the preparation environment, so the actual container build and hosted deployment must be verified on Render or a Docker-equipped machine.

## References

- [Render monorepo roots](https://render.com/docs/monorepo-support), [Blueprint settings](https://render.com/docs/blueprint-spec), [current pricing](https://render.com/pricing)
- [Vercel monorepos](https://vercel.com/docs/monorepos), [external rewrites](https://vercel.com/docs/routing/rewrites), [platform limits](https://vercel.com/docs/limits)
