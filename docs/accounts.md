# Accounts and database setup

Use MongoDB Atlas for encrypted complaints/evidence and Clerk for identity.
Clerk stores passwords and manages Google login, verification and password reset;
this app never stores passwords. MongoDB stores a minimal user record keyed by
the verified Clerk subject, with creation and last-seen timestamps.

## Local setup

1. Create an [Atlas cluster](https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/).
   Create a database user with `readWrite` on `grievance_clock`, then allow only
   your development computer's IP (and later your backend host's egress IP).
   Copy the Drivers connection string into `MONGODB_URI` in `backend/.env.local`.
   URL-encode special characters in the password. Do not use an Atlas account
   password as a database-user password or commit the URI to Git.
2. Create an application in the [Clerk dashboard](https://dashboard.clerk.com/).
   Enable Google and email/password, require email verification, and enable
   password-reset emails. Use development keys locally. Copy these settings
   into the appropriate service environment file (publishable/secret keys in `frontend/.env.local`; issuer and MongoDB settings in `backend/.env.local`; `AUTH_MODE` and `APP_ENV` in both):

   ```dotenv
   AUTH_MODE=clerk
   APP_ENV=development
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
   CLERK_SECRET_KEY=sk_test_...
   CLERK_ISSUER_URL=https://YOUR-INSTANCE.clerk.accounts.dev
   MONGODB_URI=<paste the Atlas Drivers connection string here>
   MONGODB_DATABASE=grievance_clock
   ```

   The issuer is the Clerk Frontend API URL, **not** the dashboard URL. Keep the
   exact origin you use locally in `ALLOWED_ORIGINS` (defaults include
   `http://127.0.0.1:3000` and `http://localhost:3000`).
3. Set a Fernet `DATA_ENCRYPTION_KEY` in `backend/.env.local`. Generate one with
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   only for a new database. For existing data, reuse its current key. Legacy root
   settings can be copied with `python -m scripts.split_local_env`; it preserves
   populated service settings and does not print secrets.
   Back up `DATA_ENCRYPTION_KEY` securely; losing it makes records unreadable.
4. Run `python -m scripts.check_account_config`, then restart both servers with
   `npm run dev`. Only missing setting names or connection status are printed.
5. Sign up in the app. Confirm email verification, sign out, sign back in, and
   verify your complaints return. Use a second test account to confirm isolation.

Collections are initialized by the app: `users`, `cases`, `evidence.files`, and
`evidence.chunks`. GridFS holds encrypted screenshot/document bytes; MongoDB case
payloads are encrypted too. The free Atlas tier has storage limits and no managed
backups; establish a backup plan before relying on it for real records.

## Authorization

Every private FastAPI route independently verifies the Clerk RS256 signature,
issuer, expiry, validity start, subject, session ID and authorized party (`azp`).
Pending Clerk sessions are rejected. It never trusts a user ID sent in a body or
header and never falls back to an anonymous cookie when account auth is enabled.
Tokens are read from the same-origin `__session` cookie or a Bearer header.
JWKS are fetched only from the configured HTTPS issuer, not token-supplied URLs.
Clerk rotates short-lived tokens; offline verification cannot instantly revoke a
previously issued token before its expiration.

Owner filters protect case reads, updates, deletion, evidence previews, exports
and speech endpoints. Other users' resource IDs return 404. Case updates use
revision checks to reject stale writes. There is no public admin role or endpoint
for listing all users' cases. The internal reminder scheduler scans stored cases.

## Existing local data and deployment

Previous anonymous-session data stays in `data/clock.sqlite3` and `data/evidence`.
It is not uploaded to Atlas or assigned to an account automatically. An explicit
owner mapping and migration are required if those records should be retained in
an account. Back up the database, files and encryption key together beforehand.

`AUTH_MODE=local` is an explicit development/test option using the old SQLite
browser-session behavior. With Clerk and no MongoDB URI, development can use
SQLite under verified account IDs; this is **not** cloud persistence. Production
(`APP_ENV=production`) refuses anonymous auth and missing MongoDB configuration.
Configure live Clerk keys/domain, HTTPS origins, a restricted Atlas database user,
persistent encryption key, backups and `COOKIE_SECURE=true` for deployment.
Missing sign-in keys show an unavailable page; they do not unlock private data.

Unit tests run against isolated SQLite and MongoDB test doubles, never your Atlas
cluster. Install `backend/requirements-dev.txt` to run `pytest backend/tests`.
Real provider sign-up/reset and Atlas persistence require configured accounts;
mock tests are not a substitute for those integration checks.

See [Vercel + Render deployment](DEPLOYMENT.md) for the service-specific hosting setup.
