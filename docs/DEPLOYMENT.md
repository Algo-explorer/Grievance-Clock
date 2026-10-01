# Deployment

## Reproducible local containers

Create `.env.local` from `.env.example`, then run `docker compose up --build`. Open `http://127.0.0.1:3000`. The backend is reachable only on the Compose network. The named volume persists cases and the local encryption key. Do not remove it to update the app.

Container configuration is supplied for portability; verify it in your Docker environment before hosting.

## Hosting the prototype

Use an always-on Python host with a persistent disk for the backend; an ephemeral filesystem loses cases and keys. Keep one backend worker for the prototype scheduler. The frontend can run on a Node host or Vercel with `BACKEND_URL` set before building. The backend must be reachable by the frontend proxy.

Set the actual HTTPS frontend origin in `ALLOWED_ORIGINS`, `COOKIE_SECURE=true`, `DATA_DIR` to the mounted disk and a stable `DATA_ENCRYPTION_KEY` in the hosting secret manager. Keep OpenAI and optional fraud-model credentials server-side only. Generate a Fernet key using the Cryptography library; never put it in the repository.

The backend must remain running for reminders. No SMS or WhatsApp messages are delivered by this prototype. No external government complaint is filed by the simulator.

Browser sessions are not a substitute for production identity. Review `SECURITY.md` before opening the backend to the public. A source-code repository can be public while the app and its private data remain local.

## Health and recovery

`GET /api/health` reports configuration presence, not AI quota availability. Run the synthetic smoke test to verify live provider access. API errors keep unsaved messages in the composer. The local intake fallback is explicitly selected through preferences and does not silently claim AI success.

Back up the encrypted database/files and the encryption key separately. Test restores. A missing/changed key makes existing records unreadable.
