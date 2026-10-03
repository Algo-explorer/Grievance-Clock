# Grievance Clock

**Your next step, made clear.** A workspace for investor grievances: multilingual intake, evidence preservation, fact review, deterministic routing, complaint preparation, assisted filing and event-driven follow-up.

## Deploy to Vercel and Render

Follow [the deployment guide](docs/DEPLOYMENT.md) for exact dashboard settings, environment variables, CORS and verification. Vercel uses `frontend/`; Render uses `backend/` with Docker. The root `render.yaml` can create the backend service via a Blueprint. No hosting resources are created by this repository.

```text
frontend/    Next.js app, package lock, Vercel config and UI tests
backend/     FastAPI, Python dependencies, Dockerfile and API tests
scripts/     Local launch and configuration utilities
render.yaml  Render backend Blueprint
```

## Accounts and data

Account access uses **Clerk + MongoDB Atlas**. Follow [account setup](docs/accounts.md) for keys, encryption, database access and verification. Existing anonymous local data is preserved separately, not automatically migrated.

## Run locally

Requires Node.js 22+ and Python 3.12+.

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r backend/requirements.lock.txt
# macOS/Linux: .venv/bin/python -m pip install -r backend/requirements.lock.txt
npm ci --prefix frontend
```

Copy `frontend/.env.example` and `backend/.env.example` to `.env.local` inside each service folder. For local use, set backend `APP_ENV=development` and `ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000`; configure Clerk, Atlas and the encryption key as described in [account setup](docs/accounts.md). Never commit environment files. Existing installations can run `python -m scripts.split_local_env` to copy the legacy root settings safely. AI sharing is opt-in per case. For an isolated local rehearsal without account providers, explicitly set `AUTH_MODE=local`, leave `MONGODB_URI` blank, and set `AI_MODE=demo`. In demo mode, extraction is a limited local rule parser, **not an LLM**; edit missing facts manually.

Start both services from the repository root (the launcher uses the project .venv):

```sh
npm run dev
```

Open **http://127.0.0.1:3000**. API documentation: **http://127.0.0.1:8000/docs**.

On Windows, `scripts/start.ps1` starts both servers in hidden windows, stores their process IDs in ignored `tmp/`, and prints their addresses. `scripts/stop.ps1` stops only those recorded processes after checking their command lines.

Text sends with Enter or the Send button; Shift+Enter adds a newline. The assistant tracks its current question, fills the case fields from answers, asks relevant follow-ups, and offers a review summary. Say `skip` for an unknown detail; unresolved required facts still block confirmation. Reply `confirm details` (or use the chat confirmation button) to generate the complaint and prefill the demo filing form. No external submission occurs. Explicit corrections such as `organisation: Example Securities` reopen review. Cloud failures trigger a labeled local rule-based intake response, preserving the message and case. This fallback is not an LLM and supports English/Hindi prompts; review extracted facts.

Hinglish (Hindi written in English letters) is detected automatically, or select **Hinglish** in the language menu. Local intake handles common Roman-Hindi answers, negation and amounts such as `pachis hazaar`. It preserves original messages and identifiers; ambiguous dates need clarification. This is targeted language understanding, not unrestricted transliteration. For voice, choose Hindi / Hinglish in the separate spoken-language selector; the transcript may use Devanagari and remains editable before sending.

## What works

- Responsive Next.js workspace with case dashboard, conversational intake, evidence locker, documents and timeline.
- OpenAI Responses API + Pydantic structured extraction, image evidence interpretation and response explanation; original user text is preserved separately from normalized text.
- Browser microphone recording, local Whisper small transcription and dedicated local Hindi read-aloud. Install the voice model once with `.venv\Scripts\python -m scripts.setup_local_voice`. Install Hindi playback with `.venv\Scripts\python -m scripts.setup_local_tts`. Transcript review precedes sending; raw audio is not stored. See [voice setup and licensing](docs/voice.md). Cloud transcription is a consent-controlled alternative when the local model is absent.
- English/Hindi core navigation and starter prompts; English, Hindi, Bengali, Tamil, Telugu and Marathi selection for AI responses / transcription. Secondary UI remains English. Hindi uses Piper; other languages require matching browser voices. Automatic recording language detection is independent of the chat language.
- Encrypted MongoDB case records and GridFS evidence, with SQLite available for local development. SHA-256 hashes, account ownership and optimistic concurrency checks.
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

External filing uses assisted links; the built-in portal is explicitly a simulation.

| Capability | Current implementation |
|---|---|
| Government / regulator submission | Assisted links + user-entered real acknowledgement. No live portal connector, CAPTCHA bypass, OTP handling or automatic external filing. |
| Automated demo filing | Local mock portal / API, `DEMO-` references only. |
| AI services | Implemented; require a funded and accessible OpenAI API project. Configuration alone does not establish working quota. |
| BHASHINI | Not configured. Local Whisper, optional OpenAI transcription and browser TTS are implemented. |
| Official forms | Complaint and checklist are generated; statutory ISR/transmission forms must come from the applicable institution. No invented or mislabeled forms. |
| Branch finder | Official NSDL directory link. No fabricated branch addresses or claimed nearest-branch map. |
| Notification delivery | In-app and clearly labeled local SMS/WhatsApp simulations; no outbound messaging credentials. |
| Database / authentication | Clerk verified accounts + encrypted MongoDB Atlas/GridFS. SQLite and anonymous sessions remain explicit local-test options. |
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

MongoDB stores encrypted case aggregates containing messages, evidence metadata, events, filings, responses, deadlines and notifications. Original evidence is encrypted in GridFS. Clerk subjects identify owners; no passwords are stored in the app database. Local development can use the same owner-scoped interface backed by SQLite and encrypted files.

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

UI workflow examples are in `frontend/tests/`. Run `npm --prefix frontend exec -- playwright install chromium` and `npm run test:e2e` with both servers running. The mock portal test is a fictional, local submission only.

See [integration contract](docs/INTEGRATION.md), [demo script](docs/DEMO.md), [deployment](docs/DEPLOYMENT.md), and [security notes](docs/SECURITY.md).

## Third-party components

Next.js / React / Lucide for UI; FastAPI / Pydantic for API; OpenAI for opt-in AI; ReportLab / pypdf / HarfBuzz for documents; Cryptography Fernet for storage; Noto fonts under the SIL Open Font License (see `backend/fonts/LICENSE`). No proprietary government assets or logos are copied.

### Review and evidence previews

Hinglish answers accept conversational yes/no phrasing and common spelling variants. This offline parser is still limited; cloud interpretation requires working provider quota. Original messages remain unchanged. The local formal-English draft is a summary of collected facts, not a full translation; review its notice and edit the formal fields before confirming. Screenshot previews appear in chat, the evidence locker, document review and the demo filing form. Image evidence is also embedded as an appendix in downloaded PDFs. Previews use the existing owner-scoped session and are never public image URLs. Existing confirmed drafts are preserved; review and reconfirm an older case to regenerate its wording.

Users can select multiple evidence files, replace an attachment or remove it from the current case. Any evidence change invalidates the confirmed draft and requires another fact review; original extracted facts remain available for correction. Already downloaded copies and external submissions cannot be changed. The separate filing-preview page refreshes current attachments and clears approval when the case revision changes. A complaint can be marked resolved directly, closing its open reminders while retaining the record, or permanently deleted with its evidence from the complaint controls.
