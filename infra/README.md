# Infrastructure (AWS, P5)

Proposal for the hackathon: the fewest moving parts that still run online. Everything here is a recommendation; P5 decides.

```
Browser ──► Frontend (React static build)        AWS Amplify Hosting  (or S3 + CloudFront)
   │
   └──► Backend (Next.js API) ──► Engine (Python) one EC2 host, docker compose, HTTPS via Caddy
            ▲          │              │
 Twilio ────┘          ▼              ▼
 (SMS/WhatsApp)    DynamoDB        S3 (NASA data cache, optional)
```

## Pieces

| Piece | Recommended | Why | Alternative |
|---|---|---|---|
| Frontend | **Amplify Hosting** (static, `npm run build` → `dist/`) | Git-connected deploys, HTTPS included | S3 + CloudFront |
| Backend + engine | **One EC2 instance** (e.g. t3.small) running `docker compose up -d` from the repo root | One machine to debug; engine and backend talk over the compose network; no cold starts during the demo | Backend on Amplify (Next.js SSR) + engine on ECS Fargate or a Lambda container |
| HTTPS for the API | **Caddy** in front of port 3000, with a domain pointing at the instance's Elastic IP | Twilio webhooks and the HTTPS frontend need an HTTPS API | Application Load Balancer + ACM certificate |
| Database | **DynamoDB** with two tables: `farms` (pk `farm_id`, GSI on phone) and `analyses` (pk `analysis_id`, GSI on `farm_id`) | No server to run; fits the JSON documents | RDS Postgres |
| Data cache | Local disk on EC2 first; **S3** if the engine moves off one host | Avoid re-downloading NASA data | |
| Secrets | Environment variables in `.env` on the host, later SSM Parameter Store | | |

The backend's in-memory store (`backend/lib/store.ts`) works on a single EC2 host until a restart. Move to DynamoDB before the demo so a redeploy doesn't wipe farms.

## SMS / WhatsApp

| Option | Pros | Cons |
|---|---|---|
| **Twilio** (recommended for the demo) | The webhook is already written for its format (`backend/app/api/sms/inbound`); SMS and WhatsApp on the same webhook; WhatsApp sandbox works without Meta approval | Outside AWS; paid number |
| AWS End User Messaging SMS | Stays in AWS | Two-way SMS needs an origination number that supports inbound in Romania (check availability); no WhatsApp; inbound arrives via SNS, so a different handler |

Setup with Twilio:
1. Buy a number with SMS (or use the WhatsApp sandbox).
2. Set the incoming-message webhook to `https://<api-domain>/api/sms/inbound` (HTTP POST).
3. Put `TWILIO_AUTH_TOKEN` on the host and implement the signature check (TODO in the route).

## Deploy checklist

1. EC2: Ubuntu, install Docker, clone the repo, create `.env` with `FRONTEND_ORIGIN`, `PUBLIC_APP_URL`, `TWILIO_AUTH_TOKEN`.
2. `docker compose up -d --build` and check `curl localhost:3000/api/health` → `"engine": "remote"`.
3. Caddy: `api.<domain> { reverse_proxy localhost:3000 }`. Open ports 80/443 only.
4. Amplify: connect the repo, app root `frontend`, build `npm run build`, output `dist`, env `VITE_API_URL=https://api.<domain>`, `VITE_USE_EXAMPLE=false`.
5. Add an Amplify rewrite so `/r/<id>` (SMS links) serves `index.html`.
6. Twilio webhook → `https://api.<domain>/api/sms/inbound`.
7. Before the demo: precompute the demo farm so the analysis doesn't depend on NASA APIs being fast on stage.
