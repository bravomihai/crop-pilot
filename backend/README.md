# Backend (Next.js API), owner: P5

The public API used by the React frontend and the SMS/WhatsApp webhook. It stores farms and analyses and calls the Python engine. Endpoints: [contracts/api.md](../contracts/api.md).

## Run

```bash
cd backend
npm install
cp .env.example .env.local
npm run dev
```

http://localhost:3000/api/health should return `{ "ok": true, "engine": "mock" }`.

- **Mock mode** (empty `ENGINE_URL`): `/api/analyses` returns the contract example, so P1 can integrate before the engine is ready.
- **Real mode:** run the engine (`uvicorn fieldshift.api:app --port 8000` in `engine/`) and set `ENGINE_URL=http://localhost:8000`.

## Where things are

| File | What |
|---|---|
| `app/api/farms/…` | Save / read / update a farm |
| `app/api/analyses/…` | Start an analysis, read its result |
| `app/api/sms/inbound/route.ts` | SMS/WhatsApp webhook (Twilio format) |
| [lib/store.ts](lib/store.ts) | **In-memory** storage. Replace with DynamoDB, same signatures |
| [lib/engine.ts](lib/engine.ts) | Engine client + mock |
| [lib/analyses.ts](lib/analyses.ts) | Shared "run an analysis" used by the API and SMS |
| [lib/sms.ts](lib/sms.ts) | SMS commands and the summary text |

## Testing SMS locally

```bash
curl -X POST http://localhost:3000/api/sms/inbound -d "From=+40700000000" -d "Body=rezultat"
```

The phone number must belong to a saved farm (`contact.phone_e164`).

## TODO (P5)

- DynamoDB instead of memory (data is lost on restart, and serverless instances don't share memory).
- Verify the Twilio webhook signature.
- Deploy (see [infra/README.md](../infra/README.md)).
- End-to-end check: form → farm → analysis → results → SMS.
