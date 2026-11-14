# Current architecture

```text
Browser (React in Next.js)
  POST /api/recommendations
        │ validates the request and generates request_id
        ▼
Next.js backend ── HTTP + internal token ──► FastAPI
        │                                    pipeline
        │                         data_service → evaluator → recommender
        ◄──────── validated JSON result ─────────┘
        │
        ▼
Three plans + calendars + trade-offs + sources + data gaps

PostgreSQL/Prisma: optional public-data cache, accessed only through Next.js.
```

There are no accounts, persistent sessions, saved farms, or historical analyses to retrieve.
This version has no job queue: calculation uses request/response, an explicit timeout,
and reusable cached data. Add a queue only if actual execution times require it;
do not persist farmer data in anticipation of an unrequested use case.

## Agricultural time

`crop_count=3` means three successive main crops, not three years or three harvests
of the same crop. An autumn crop crosses calendar years. Check the end of harvest
before the next sowing starts. Do not assume a repeating C→A transition after the last
step. Cover crops and perennial crops are future extensions.

## Data and uncertainty

The location is a point: do not claim field-level measurements or within-field analysis.
POWER provides regional context. Preserve daily data and metadata for crop-specific
windows; annual averages do not replace exposure during sensitive periods.
User-entered soil information retains its source. Missing history leaves rules
unverified; it does not imply that the field had no previous crops.

## Modes

- `NEXT_PUBLIC_USE_MOCK_API=true`: independent frontend using a fixed, visibly labelled fixture.
- `ENGINE_MODE=demo`: real backend and Python service, but explicitly labelled fictional plans.
- `ENGINE_MODE=computed`: real-data integration; returns 503 when required data/modules
  are unavailable. It never falls back automatically to fictional results.

## Retained data

Prisma contains only `DataCache`: key, namespace, public payload, and expiration.
Geographic search results and NASA series may be reused. Do not save requests,
results, crop histories, phone numbers, email addresses, or user identifiers.
Do not log payloads or tokens.

## Language

Project documentation, interface text, and generated explanations use English.
Localized provider responses use English and language-specific cache keys.
Geographic proper names and original source identifiers retain their spelling.
