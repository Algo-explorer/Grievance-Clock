# Grievance Clock

**Your next step, made clear.** A SANGYAN Track B prototype for investor grievances: multilingual intake, evidence preservation, fact review, deterministic routing, complaint preparation, assisted filing and event-driven follow-up.

## Run locally

Requires Node.js 22+ and Python 3.12+.

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r backend/requirements.lock.txt
# macOS/Linux: .venv/bin/python -m pip install -r backend/requirements.lock.txt
npm ci
```

Copy `.env.example` to `.env.local` and configure the server-only settings. Never commit `.env.local`. AI sharing is opt-in per case. Set `AI_MODE=demo` for a no-key, no-network rehearsal. In demo mode, extraction is a limited local rule parser, **not an LLM**; edit missing facts manually.

Start both services from the repository root (the launcher uses the project .venv):

```sh
npm run dev
```

Open **http://127.0.0.1:3000**. API documentation: **http://127.0.0.1:8000/docs**.

On Windows, `scripts/start.ps1` starts both servers in hidden windows, stores their process IDs in ignored `tmp/`, and prints their addresses. `scripts/stop.ps1` stops only those recorded processes after checking their command lines.

Text sends with Enter or the Send button; Shift+Enter adds a newline. Cloud failures trigger a labeled local rule-based intake response, preserving the message and case. This fallback is not an LLM and supports English/Hindi prompts; review extracted facts.

## What works

- Responsive Next.js workspace with case dashboard, conversational intake, evidence locker, documents and timeline.
- OpenAI Responses API + Pydantic structured extraction, image evidence interpretation and response explanation; original user text is preserved separately from normalized text.
- Browser microphone recording, local Whisper transcription and browser read-aloud. Install the voice model once with `.venv\Scripts\python -m scripts.setup_local_voice`. Transcript review precedes sending; raw audio is not stored. Cloud transcription is a consent-controlled alternative when the local model is absent.
- English/Hindi core navigation and starter prompts; English, Hindi, Bengali, Tamil, Telugu and Marathi selection for AI responses / transcription. Secondary UI remains English. Browser TTS voices vary by device.
- Encrypted SQLite case aggregates and encrypted original evidence. SHA-256 hashes, owner-scoped sessions and optimistic concurrency checks.
- JPG/PNG/WebP, PDFs and TXT intake, with local OCR for images and the first five pages of scanned PDFs. Review OCR results; local OCR language coverage is limited.
- User confirmation invalidated whenever facts/evidence change. Complaint letter, printable offline checklist and ZIP dossier with unchanged original files.
- Deterministic routing and calendar-day calculations in Asia/Kolkata, with source/version metadata.
- Labeled local portal simulation, explicit approval, idempotent acknowledgements and an example Playwright demo workflow.
- Real acknowledgements can be entered by the user. They are marked **user-reported**, never represented as independently verified filings.
- Response explanation, resolved/unresolved decisions, review-window eligibility and reuse of an existing case for escalation.
- Durable in-app reminder records, checked each minute while the backend is running; simulated SMS/WhatsApp reminders stay in the app.
- Optional, explicitly approved teammate fraud-model adapter. Failure does not block the grievance workflow.
- Three fictional demo scenarios: Telegram scam, delayed broker payout, and share transmission.

## Deliberate integration boundaries

This is a working **hackathon prototype**, not a production complaint-filing service.

| Capability | Current implementation |
|---|---|
| Government / regulator submission | Assisted links + user-entered real acknowledgement. No live portal connector, CAPTCHA bypass, OTP handling or automatic external filing. |
| Automated demo filing | Local mock portal / API, `DEMO-` references only. |
| AI services | Implemented; require a funded and accessible OpenAI API project. Configuration alone does not establish working quota. |
| BHASHINI | Not configured. Local Whisper, optional OpenAI transcription and browser TTS are implemented. |
| Official forms | Complaint and checklist are generated; statutory ISR/transmission forms must come from the applicable institution. No invented or mislabeled forms. |
| Branch finder | Official NSDL directory link. No fabricated branch addresses or claimed nearest-branch map. |
| Notification delivery | In-app and clearly labeled local SMS/WhatsApp simulations; no outbound messaging credentials. |
| Database / authentication | Encrypted SQLite + browser-session ownership; no Supabase account or hosted database is required. Losing the cookie loses access to the session. |
| Deployment | Docker configuration and deployment instructions supplied. An always-on backend and persistent storage are required. |

## Architecture

```text
Next.js / React client
  └─ same-origin /api proxy
       └─ FastAPI modular application
            ├─ intelligence.py   LLM extraction, transcription, explanations
            ├─ models.py         validated request and fact contracts
            ├─ engine.py         deterministic routes, events and clocks
            ├─ rules.json        source-linked regulatory rules
            ├─ documents.py     complaint / offline PDF generation
            ├─ storage.py       owner isolation, encryption, CAS persistence
            └─ main.py          API, workflow transitions, scheduler, adapters
```

The model cannot write a deadline, choose a filing state, submit externally or set an acknowledgement. Those transitions are server-controlled. An AI classification is still an interpretation: **the user must check facts and category before filing**.

SQLite stores encrypted case aggregates containing messages, evidence metadata, events, filings, responses, deadlines and notifications. Originals are separate encrypted files. This intentionally keeps one deployable backend; the API contracts allow a later PostgreSQL/Supabase migration.

## Rules and sources

Rules reviewed on **1 October 2026**. Review them before production use.

- [SCORES FAQ](https://scores.sebi.gov.in/faqs): raise the grievance with the entity first; the entity ATR period on SCORES is 21 calendar days from receipt. First/second review windows are 15 calendar days from the corresponding ATR. The app does not apply a universal 21-day deadline to every initial broker email.
- [National Cybercrime Reporting Portal](https://cybercrime.gov.in/): transferred-money cyber fraud is urgent. Call **1930** and contact the bank without waiting for a complete dossier.
- [SMART ODR](https://smartodr.in/): eligibility/process discovery link; ODR is not presented as an automatic next-day escalation.
- [Official NSDL directory](https://nsdl.com/participant/securities-company-search): verify your own DP/registrar and branch details.
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): schema-constrained interpretation. This constrains structure, not factual accuracy.

Personal reminders (one or seven days) are labeled non-regulatory. Clocks derive from recorded events, use Indian calendar dates and expire at the end of the stated due date. The acknowledgement/response date must be checked by the user against the official portal.

## Tests

```sh
.venv\Scripts\python -m pytest backend/tests -q
npm run typecheck
npm run build
```

Optional synthetic live-provider smoke test (may incur API charges):

```sh
.venv\Scripts\python -m scripts.smoke_ai
```

UI workflow examples are in `tests/`. Run `npx playwright install chromium` and `npm run test:e2e` with both servers running. The mock portal test is a fictional, local submission only.

See [integration contract](docs/INTEGRATION.md), [demo script](docs/DEMO.md), [deployment](docs/DEPLOYMENT.md), and [security notes](docs/SECURITY.md).

## Third-party components

Next.js / React / Lucide for UI; FastAPI / Pydantic for API; OpenAI for opt-in AI; ReportLab / pypdf / HarfBuzz for documents; Cryptography Fernet for storage; Noto fonts under the SIL Open Font License (see `backend/fonts/LICENSE`). No proprietary government assets or logos are copied.
