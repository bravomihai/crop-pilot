# API v1

Contract source: `packages/contracts/src/index.ts`.
Python consumes the generated schemas in `packages/contracts/schemas/`.
Examples: `packages/contracts/examples/`.

| Method | Web route | Purpose |
| --- | --- | --- |
| GET | `/api/locations?q=Calarasi` | Locality options with coordinates from Open-Meteo/GeoNames |
| POST | `/api/recommendations` | Complete form → result in the same request |
| GET | `/api/engine/status` | Engine connectivity, mode, and contract compatibility; no agronomic calculation |
| GET | `/api/health` | Service identity/contract version; does not check external services |
| POST | `/api/summary` | Optional English-only OpenAI summary of a computed result, `{result}`; 503 `summary_not_configured` without `OPENAI_API_KEY`. Body ≤ 256 KB; the gateway allows 6/min per IP (burst 2) |

There are no endpoints for users, authentication, farms, or saved results. Calculation
does not require login. Next.js validates the schema and at least one positive priority.

Errors: `{code,error,request_id}`. `400` invalid form, `413` oversized request,
`422 unsupported_location` (point outside Romania or invalid field outline, rejected by
the engine), `499 request_cancelled` (the browser cancelled the request; the engine call
is aborted too), `502` unreachable engine/invalid response, `503` unconfigured/unimplemented engine.

An availability date before today is not rejected: the engine plans from today and says
so as the first assumption, so no plan starts in the past. Inputs that have no effect (an
irrigation limit with irrigation off, a crop shortlist with `selected_crops_only` false,
shortlisted crops without rules or also excluded) are reported in `assumptions`.
Responses contain no stack traces or connection details. Results are not cached by
the browser or proxy. Display text uses English; location search requests English
provider labels and includes the language in its public-data cache key.

## Internal Python service

`POST /recommendations`: the same request JSON, `Authorization: Bearer <INTERNAL_API_TOKEN>`,
and `X-Request-ID`. Configure the token in both services, on the server only.
`GET /health`: version and configured mode; it does not prove that the engine is validated.

Public-data cache for P2: `GET/PUT /api/internal/cache/environment:<sha256>` with the same
token. A `404` means a cache miss. Cache failure does not prevent direct source access.

## Result

`mode`: `demo` or `computed`. `status`: `complete` (3 plans), `limited` (1–2),
`insufficient_data` (0). Each plan contains three steps, ISO windows, benefits,
trade-offs, an explanation, a confidence level, and source references. Confidence
levels are not calibrated probabilities of success. The frontend explicitly labels `mode: demo`.

## Optional fields (contract 1.0, added 2026-11-14)

All fields below are optional: older requests/results remain valid, and consumers
that do not use these fields need no changes. Complete examples:
`packages/contracts/examples/recommendation-request.full.json` and `recommendation-result.full.json`.

| Field | Location | Producer / consumer |
| --- | --- | --- |
| `current_rotation: crop_id[1–5]` | request | P1 collects it; P4 continues the cycle for three crops and evaluates it |
| `history[].source: typed\|apia\|spray_records\|satellite\|unknown` | request | P1 submits it; P4 lowers confidence for inferred history |
| `priorities.productivity: 0–5` | request | P1 collects the priority; P3 supplies the `productivity` score; P4 weights it |
| `baseline: plan` | result | P4 returns it only when `current_rotation` exists; excluded from `status` counts |
| `plan.scores: {water, soil, climate, productivity}` | result | P3 calculates 0–1 or `null` (unknown); P4 forwards it; P1 displays it |
| `plan.local_checks: string[]` | result | P3/P4 describe local checks; P1 displays them |
| `plan.violations: string[]` | result | Baseline only: rules broken by the current rotation |
| `money_inputs: {prices_lei_per_t, costs_lei_per_ha}` | request | P1 collects the farmer's own price and cost per crop for the money estimate; not stored |
| `plan.economics` | result | P3 estimates lei per hectare and year (income, costs, CAP payments, margin; ranges, `null` = unknown); not a forecast and not used for ranking; P1 displays it |

`productivity` is relative potential (EcoCrop, FAO GAEZ), not a yield or profit forecast. `economics`
is a rough estimate from county yield statistics, past regional prices, published cost budgets and
reported CAP payment rates (see `docs/economics-design.md`); it is not a forecast either.

## Future integration

SMS/WhatsApp are not implemented. Future adapters must collect the same inputs and
use this contract. Do not assume accounts or Twilio APIs. Do not send messages or
modify existing webhooks in other services.

## Engine connection status

`GET /api/engine/status` checks server configuration and calls Python `/health`,
with a 3-second deadline including response-body reading. It does not use the cache,
perform calculations, or call NASA. Redirects are not followed.

Example 200 response:

```json
{"status":"reachable","service":"croppilot-engine","contract_version":"1.0","mode":"demo","request_id":"<uuid>"}
```

`reachable` confirms only connectivity and response shape/version. `computed` is
reported when configured but does not guarantee that P3/P4 are ready. Python `/health`
does not authenticate the token; this endpoint checks only the presence and length
of the web token, not whether the two services' secrets match.

Errors: `503 engine_not_configured` for missing/invalid configuration;
`502 engine_unavailable` for a failed connection or unsuccessful HTTP status;
`502 invalid_engine_status` for invalid JSON or a different service/contract/mode;
`504 engine_timeout` for an exceeded deadline. Every response has `Cache-Control:
no-store` and `X-Request-ID`, matching the body's `request_id`. The internal URL and
token are never returned. This check does not depend on the PostgreSQL cache.

Backend checks without external services: `pnpm test:backend` (includes a temporary
localhost HTTP server to test timeouts).

## Consolidated backend behavior — P5

All implemented Route Handlers return `Cache-Control: no-store` and `X-Request-ID`.
For calculation, the ID is forwarded to Python and checked in its result. Errors
also include it in the body. Unsupported methods remain handled automatically by Next.js.

`POST /api/recommendations` accepts `application/json`, up to 32 KiB.
`ENGINE_TIMEOUT_MS` must be an integer between 100 and 90000 ms; invalid configuration
returns 503. The timeout includes response-body reading. Engine redirects are not
followed. Result JSON is limited to 2 MB and checked against the contract and semantic
rules. Mismatched IDs/locations, overlapping calendars, sowing before `available_from`,
and excluded crops are rejected.

`GET /api/locations` validates both provider and cached data. Invalid cached results
are ignored. The timeout is 10 seconds; the external body is limited to 128 KB.
No matches is a valid empty-list result.

Additional codes: `415 unsupported_media_type`, `504 engine_timeout`,
`504 geocoding_timeout`, `502 invalid_geocoding_result`. Connection failures return
502. An engine returning 503 for calculation produces `503 engine_not_ready`, without fallback.

### Internal public-data cache

`GET/PUT /api/internal/cache/environment:<sha256>` requires exactly the header
`Authorization: Bearer <token>`. PUT accepts a JSON object up to 2 MB and returns
204 only after a successful write; disabled/unavailable cache returns 503.
A GET with no unexpired data returns 404. These responses are not HTTP-cached.

`DELETE /api/internal/cache`, with the same token, deletes at most 1000 expired
entries and returns `{deleted,batch_size:1000}`. Disabled cache means zero deletions;
unavailable cache returns 503. The Compose `cache-maintenance` service calls it at
startup and hourly, with at most 100 batches per run. Active data is retained.
Database connection/query deadlines are 1 second. Failed reads behave as cache misses;
geocoding and NASA data may use the external source without the cache.

### Public access and logs

The NGINX entry point on local port 8080 applies per-IP limits: 5 calculations/minute
(burst 3), 60 searches/minute (burst 10), and 30 engine status checks/minute (burst 5).
Exceeding a limit returns 429 JSON, `Retry-After: 60`, `X-Request-ID`, and `no-store`.
Oversized bodies receive 413 JSON. `/api/internal` and its subroutes are blocked at
this entry point even with a valid token. In production, only Caddy is public and
direct service ports are removed. These limits do not apply to development port
3000; do not expose it publicly.

Application logs contain `event`, a static operation name, `request_id`, status,
an error code when applicable, and `duration_ms`. They contain no request bodies,
URLs, tokens, or raw exception messages. No analysis history is created. Logs go to
standard output with Docker rotation; they are not an alerting or server-monitoring system.
