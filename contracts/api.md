# API

Two HTTP layers:

- **Public API: Next.js backend (P5).** Used by the React frontend and the SMS/WhatsApp webhook.
- **Internal API: Python engine.** Called only by the backend. It wraps the data service (P2), evaluator (P3) and recommender (P4), which run in one process.

All bodies are JSON and use the formats in [schemas/](schemas/).

## Public API (backend, `/api`)

| Method | Path | Body | Response |
|---|---|---|---|
| `POST` | `/api/farms` | `FarmRequest` (without `farm_id`) | `201 { "farm_id": "..." }` |
| `GET` | `/api/farms/{farm_id}` | | `FarmRequest` (with `farm_id`) |
| `PUT` | `/api/farms/{farm_id}` | `FarmRequest` | `200 { "farm_id": "..." }` |
| `POST` | `/api/analyses` | `{ "farm_id": "...", "priorities"?: {...}, "scenario"?: {...} }` | `202 { "analysis_id": "...", "status": "running" }` |
| `GET` | `/api/analyses/{analysis_id}` | | `{ "status": "running" \| "done" \| "failed", "result"?: AnalysisResult, "error"?: "..." }` |
| `POST` | `/api/sms/inbound` | Provider webhook (form-encoded) | Reply message |
| `GET` | `/api/health` | | `{ "ok": true }` |

`priorities` and `scenario` in `POST /api/analyses` override the saved farm values. The frontend uses them for the what-if sliders without saving the farm again.

**Polling:** the frontend polls `GET /api/analyses/{id}` every ~1.5 s until `status` is `done` or `failed`. If the engine answers in under ~10 s the backend may run it inline and return `200` with the result directly. The frontend must handle both.

**Errors:** `{ "error": "message", "code": "validation_error" | "not_found" | "engine_error" | "data_unavailable" }` with a matching HTTP status.

## Internal API (engine)

| Method | Path | Body | Response |
|---|---|---|---|
| `POST` | `/analyze` | `FarmRequest` (with `farm_id`) | `AnalysisResult` |
| `POST` | `/field-data` | `{ "lat", "lon", "start_year", "end_year" }` | `FieldData` (debugging, and lets P2 work alone) |
| `POST` | `/evaluate` | `{ "farm": FarmRequest, "rotation": [...], "cover_crops"?: [...] }` | `Evaluation` (debugging) |
| `GET` | `/health` | | `{ "ok": true }` |

The engine caches `FieldData` per (rounded location, period), so re-running with new priorities or a new scenario is fast.

## SMS / WhatsApp flow

The farm is created once in the web app with a phone number (`FarmRequest.contact`). After that, the farmer can talk to the app by SMS. The backend maps the phone number to the farm.

| Farmer sends | App does | App replies |
|---|---|---|
| `REZULTAT` | Returns the latest analysis | Summary + link |
| `ANALIZA` | Starts a new analysis with saved settings | "Analizăm…", then the summary when done |
| `APA` / `SOL` / `VENIT` | Re-runs with that priority set highest | Summary + link |
| `SECETA` | Re-runs with `rain_change_pct: -20` | Summary + link |
| `AJUTOR` | | List of commands |
| Anything else | | List of commands |

Matching is case-insensitive and ignores diacritics.

**Summary format.** Keep it to 2 SMS segments. Romanian diacritics switch SMS to UCS-2 encoding, which allows 70 characters per segment instead of 160. So either strip diacritics in SMS or keep the text very short. WhatsApp has no such limit.

```
FieldShift: 1) Soia-grau-porumb +masariche (73/100)
2) Grau-sorg-soia (67) 3) Actuala porumb-porumb-grau (53)
Detalii: https://<app>/r/an_demo_001
```

**Provider:** see [../infra/README.md](../infra/README.md). The webhook handler should be provider-agnostic: parse the inbound message into `{ from, text, channel }` first, then handle commands.
