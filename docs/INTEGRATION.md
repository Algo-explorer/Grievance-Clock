# Team integration contract

The assistant runs independently of the fraud model. All case operations require its HttpOnly session cookie. The frontend uses a same-origin proxy; do not expose an API key to a browser.

## Fraud model adapter

Set `FRAUD_API_URL` to your team’s exact POST endpoint and `FRAUD_API_TOKEN` on the backend. A user must approve analysis in the evidence screen before the adapter is invoked.

Request:

```json
{"text":"User-reviewed grievance description","evidence_ids":["opaque-evidence-id"]}
```

Response:

```json
{"risk_score":0.94,"category":"investment_impersonation","signals":["guaranteed_return","telegram_contact"]}
```

Score must be 0–1. Maximum 30 signals. The adapter has a ten-second timeout, does not follow redirects, and does not transmit original files. Evidence IDs are correlation identifiers, not URLs or cross-user download grants. For image models, agree a separate consented file-transfer contract before extending this adapter.

Results are retained with provider provenance but cannot override deterministic routes, legal dates or submission status. An unavailable model returns a clear error without changing the case.

## Assistant API

| Method / path | Purpose |
|---|---|
| POST `/api/session` | Issue a private session cookie |
| POST `/api/cases` | Create case with language and AI-sharing preference |
| GET `/api/cases` | List only the session’s cases |
| POST `/api/cases/{id}/messages` | Preserve original message and extract proposed facts |
| PUT `/api/cases/{id}/facts` | Confirm full facts with current revision |
| POST `/api/cases/{id}/evidence` | Upload original multipart `file` |
| POST `/api/cases/{id}/transcribe` | Transcribe multipart audio; return editable text |
| POST `/api/cases/{id}/fraud-analysis` | Explicitly requested team analysis |
| POST `/api/cases/{id}/simulate` | Approved local demo filing |
| POST `/api/cases/{id}/acknowledgements` | Record user-reported real filing |
| POST `/api/cases/{id}/responses` | Explain response and derive appropriate clock |
| POST `/api/cases/{id}/decision` | Resolve or mark unsatisfied |
| POST `/api/cases/{id}/escalate` | Prepare eligible next representation |
| GET `/api/cases/{id}/documents/{kind}` | `complaint.pdf`, `offline.pdf`, `dossier.zip` |
| DELETE `/api/cases/{id}` | Remove case + encrypted evidence |

OpenAPI is served at `/openapi.json`, interactive documentation at `/docs` on the backend.

Facts use `backend/models.py:Facts`. Extraction includes the previous fact set, but user text and evidence are untrusted data. All changes invalidate previous fact confirmation. Use `revision` for confirmation / submission and refresh after HTTP 409.

## Embedding

Run the assistant alongside the ML project and proxy `/api` to FastAPI. Reuse the UI components or link into the assistant’s workspace. For a shared login in production, replace session ownership with a verified identity provider and enforce ownership on every case/file query. Do not pass session credentials in URL query parameters.
