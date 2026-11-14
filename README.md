# FieldShift — calculator pentru succesiunea culturilor

NASA Space Apps 2026 · Field Shift: Adapting Farms with NASA Data.

Fermierul introduce localitatea/un punct, data disponibilității, ce a cultivat, informații
de sol dacă le are și prioritățile sale. Primește trei planuri pentru următoarele trei
culturi principale, cu ferestre de semănat/recoltare și compromisuri. Nu își face cont.
Nu salvăm profiluri sau analize personale. O nouă vizită înseamnă un formular nou.

**Starea actuală:** mediu de dezvoltare și integrare demonstrativă. Evaluarea agronomică
și optimizarea sunt pentru P3/P4. Rezultatele demo sunt fictive și marcate în interfață.
Modul `computed` nu este încă disponibil. Nu sunt recomandări validate pentru cultivare.

## Structură

| Director             | Rol                                                                     |
| -------------------- | ----------------------------------------------------------------------- |
| `apps/web`           | Next.js + React, formular și API public, Prisma/PostgreSQL pentru cache |
| `services/engine`    | FastAPI și module Python pentru P2/P3/P4                                |
| `packages/contracts` | Sursa Zod, tipuri TS, scheme JSON generate, exemple                     |
| `docs`               | Arhitectură, API, responsabilități, status                              |
| `infra`              | AWS și reverse proxy                                                    |

Începe cu [AGENTS.md](AGENTS.md), [docs/team.md](docs/team.md) și [contractul API](docs/api.md).

## Instalare locală

Node 22, pnpm 10.11.0, Python 3.11+, uv 0.9.5 și, opțional, Docker pentru PostgreSQL.

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm contracts:generate
pnpm db:generate
cp apps/web/.env.example apps/web/.env.local
cp services/engine/.env.example services/engine/.env
uv sync --project services/engine --frozen --extra dev
```

În două terminale, când doriți să porniți aplicația:

```sh
# Terminal 1
cd services/engine
.venv/bin/uvicorn fieldshift.api:app --env-file .env --reload --port 8000
```

```sh
# Terminal 2, de la rădăcină
pnpm dev
```

Web: `http://localhost:3000`. Motorul este intern. Tokenul trebuie să fie identic în
cele două fișiere de mediu. Configurația implicită locală este `ENGINE_MODE=demo`.

### Frontend independent

Setează `NEXT_PUBLIC_USE_MOCK_API=true` în `apps/web/.env.local`, apoi pornește doar web-ul.
`src/lib/api.ts` citește fixture-ul comun. Formularul nu este evaluat în acest mod și
calendarul exemplului este fix; interfața afișează avertismentul. Harta și căutarea
localităților folosesc internet; poți selecta punctul fără căutare.

### Cache PostgreSQL

Cache-ul este opțional și conține date publice, nu formulare/rezultate de fermieri.

```sh
cp .env.example .env
# Configurează valorile locale înainte de pornire.
docker compose up -d postgres
# Prisma CLI citește apps/web/.env; Next.js citește și .env.local.
cp apps/web/.env.example apps/web/.env
pnpm db:deploy
```

Setează `CACHE_ENABLED=true` în mediul web. Pentru toate serviciile în containere:
`docker compose up --build`. Migrarea locală este un serviciu separat din Compose.
Nu folosi credențialele demonstrative pe un deployment comun.

## Verificări

```sh
pnpm contracts:generate
pnpm db:generate
pnpm typecheck
pnpm test:backend
# Cu PostgreSQL local și DATABASE_URL configurat:
pnpm test:cache
services/engine/.venv/bin/python -m pytest services/engine/tests
```

[Starea exactă și limitele](docs/status.md). SMS prin Anveo și WhatsApp prin Meta sunt
în afara acestei versiuni. Nu există Twilio, login, SQS sau stocare de ferme în acest repo.

Dependențele sunt fixate în `pnpm-lock.yaml` și `services/engine/uv.lock`.
Instalarea uv: https://docs.astral.sh/uv/getting-started/installation/ .

## Backend P5

Intrarea locală cu limite de cereri este `http://localhost:8080` când pornești întregul
Compose. Cache-ul public se curăță automat. Verificările de integrare și profilul HTTPS
sunt în [infra/README.md](infra/README.md); configurația pentru publicarea ulterioară este
în [infra/aws/README.md](infra/aws/README.md). Workflow-ul pregătit în
`.github/workflows/checks.yml` va rula după publicarea modificărilor pe GitHub.
