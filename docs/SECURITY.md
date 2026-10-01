# Security and privacy boundaries

- `.env.local`, database files, uploaded evidence, encryption keys, logs and generated packs are excluded from Git and Docker build contexts.
- Fernet authenticates and encrypts every case payload and original evidence blob at rest. A local installation generates a key in `data/encryption.key`; hosted deployments should set `DATA_ENCRYPTION_KEY` through a secret manager and keep it separate from database backups.
- Session tokens are random, hashed in SQLite, HttpOnly and SameSite=Strict. Configure secure cookies and HTTPS when hosted. Session ownership is a prototype identity mechanism, not verified identity or an account-recovery system.
- Every case/document/file query checks the owner. Evidence is never served from a public static directory. Downloads are authenticated responses, not public URLs.
- Updates use a revision compare-and-swap to avoid lost writes. Submission idempotency keys prevent duplicate demo filings.
- Uploads have size/count limits and content parsing checks. Originals remain unchanged. Encrypted or malformed PDFs are rejected. Text extraction is not a malware scanner; use a sandboxed scanner before deploying for untrusted public uploads.
- UI renders model/user text as text, not HTML. PDF paragraphs escape markup. Download names use generated safe identifiers.
- Model output is schema-validated and cannot create clocks or filing events. Source documents are framed as untrusted input. User confirmation is still essential; structured output does not guarantee truth.
- AI sharing is opt-in. Original text is retained to avoid overwriting testimony with a translation. Provider error text and credentials are not logged to users. Model calls set `store=False`; provider retention policies still apply.
- Simple text screening rejects obvious OTP/PIN/password patterns. It is not a comprehensive DLP guarantee. Avoid collecting secrets at all.
- The frontend has origin checks, no-store API responses and non-sniffing headers. Per-session AI rate limiting is in-memory and is not a distributed abuse-control system.
- A deleted case and its evidence are removed from the live store. Backups, SQLite free pages and operating-system storage may retain encrypted remnants; this is not a claim of forensic secure erasure.

Before public production use: verified authentication + recovery, HTTPS, bounded request-body enforcement at a reverse proxy, distributed rate limits and spend controls, malware scanning, backup/restore and key rotation procedures, retention policy, accessibility review, observability without sensitive logs, legal/rule review and authorized portal integrations.
