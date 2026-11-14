# FieldShift: crop rotation planning with NASA data

NASA Space Apps Challenge 2026 · **Field Shift: Adapting Farms with NASA Data**

Farmers in Romania choose the next crops for a field mostly from habit and last year's
prices, while summers get hotter and dry spells longer. FieldShift helps them compare
**what they do today** with **three alternative sequences of the next three main crops**,
using the field's own recent weather from NASA and a climate what-if.

For each option the farmer sees:

- the sowing and harvest windows of every crop;
- how it scores on **water**, **soil**, **climate** risk and **productivity** potential;
- why it was suggested, what it costs (trade-offs) and how sure we are;
- **what to check locally** with an agronomist before acting on it.

It supports the farmer's and the agronomist's judgement. It does not replace it, and it
does not forecast yields or profit.

## How it works

```text
Farmer: location, field available from, crop history, current rotation,
        soil (if known), irrigation, excluded crops, priorities, what-if scenario
   │
   ▼
1. Field data (P2)      NASA POWER daily weather for the last ~20 seasons, FAO-56 ET0,
                        ISRIC SoilGrids soil; data gaps are reported, never filled in
   │
   ▼
2. Evaluation (P3)      regional crop rules (calendars, successions, return intervals)
                        decide what is feasible; each sequence is replayed over the past
                        seasons and the what-if to score water, soil, climate, productivity
   │
   ▼
3. Recommendation (P4)  candidate sequences, farmer weights, trade-offs (Pareto),
                        three distinct plans + the current rotation as a baseline,
                        explanations and confidence built only from the evaluation
   │
   ▼
Results: plans and baseline side by side, calendars, scores, sources, local checks
```

What keeps it honest:

- **Transparent scoring, not a trained model, makes the decision.** There is no dataset
  of "the right rotation", and the answer depends on the farmer's priorities. Rules and
  sourced scores can be explained and checked.
- **Replay instead of averages.** A sequence is played over each of the field's recent
  seasons, so a plan that fails in dry years shows it.
- **Unknown is not neutral.** Missing data gives `null` scores, lower confidence and a
  question for the agronomist, never a default value.
- **Regional data is context.** NASA POWER and SoilGrids describe the area around the
  point, not the field itself. The app asks for a point, not a field boundary.
- **The what-if is a scenario, not a forecast.** Temperature and rain sliders show how
  sensitive each plan is.

## Coverage

Crop rules are regional: sowing dates in the Romanian Plain are not those of
Transylvania. Version 1 covers the **southern and south-eastern plains** (Romanian
Plain, Bărăgan, Dobrogea) with the main field crops: winter wheat, winter barley, maize,
sunflower, pea, plus rapeseed and soybean when their rules are sourced. For points
outside a covered zone the app says so (`insufficient_data`) instead of guessing.

Next zones: the Western Plain, Moldova and Transylvania. Later: cover crops between main
crops, multi-year forage (alfalfa), SMAP soil moisture, SRTM slope, CMIP6 scenarios and a
Sentinel-2 crop-history classifier for farmers who don't know their field's history.

## Current status

The web app, the API, the contract, the NASA POWER adapter and the recommender (tested
with a synthetic evaluator) are written. The regional rules and the evaluator are in
progress. Until they are done, the app runs in **demo mode** with invented, clearly
labelled plans. Details: [docs/status.md](docs/status.md).

## Repository

| Folder               | What it holds                                                   | Owner  |
| -------------------- | --------------------------------------------------------------- | ------ |
| `apps/web`           | Next.js + React: form, map, results, public API, optional cache | P1, P5 |
| `services/engine`    | Python FastAPI: `data_service`, `evaluator`, `recommender`      | P2–P4  |
| `packages/contracts` | Zod contract, generated JSON Schemas, examples                  | all    |
| `docs`               | Architecture, API, team split, status                           |        |
| `infra`              | AWS deployment and reverse proxy                                | P5     |

Start with [AGENTS.md](AGENTS.md), [docs/team.md](docs/team.md) and [the API](docs/api.md).
The contract lives in [`packages/contracts/src/index.ts`](packages/contracts/src/index.ts);
[`recommendation-request.full.json`](packages/contracts/examples/recommendation-request.full.json)
and [`recommendation-result.full.json`](packages/contracts/examples/recommendation-result.full.json)
show every optional field.

## Run locally

Node 22, pnpm 10.11.0, Python 3.11+, uv 0.9.5, and Docker only for the optional cache.

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm contracts:generate
pnpm db:generate
cp apps/web/.env.example apps/web/.env.local
cp services/engine/.env.example services/engine/.env
uv sync --project services/engine --frozen --extra dev
```

Then, in two terminals:

```sh
# Terminal 1: engine
cd services/engine
.venv/bin/uvicorn fieldshift.api:app --env-file .env --reload --port 8000
```

```sh
# Terminal 2: web, from the repository root
pnpm dev
```

Open `http://localhost:3000`. The internal token must be the same in both env files.
The example settings run the real engine (`ENGINE_MODE=computed` with
`ENABLE_NASA_POWER=true`). Set `ENGINE_MODE=demo` for clearly labelled fictional plans without
internet access. Before a demo, download the demo field once:
`FIELDSHIFT_CACHE_DIR=cache .venv/bin/python -m fieldshift.warm 44.45,26.5` (from `services/engine`).

**Frontend only:** set `NEXT_PUBLIC_USE_MOCK_API=true` in `apps/web/.env.local` and run
only `pnpm dev`; the app reads the shared example.

**Optional PostgreSQL cache** (public data only, never farmer input or results):

```sh
cp .env.example .env
docker compose up -d postgres
cp apps/web/.env.example apps/web/.env
pnpm db:deploy
```

Then set `CACHE_ENABLED=true` for the web app. Everything in containers:
`docker compose up --build`.

## Checks

```sh
pnpm contracts:generate
pnpm db:generate
pnpm typecheck
pnpm test:backend
# With local PostgreSQL and DATABASE_URL configured:
pnpm test:cache
services/engine/.venv/bin/python -m pytest services/engine/tests
```

## Data sources

[NASA POWER](https://power.larc.nasa.gov/) daily agro-meteorology ·
[ISRIC SoilGrids](https://soilgrids.org/) · [FAO-56](https://www.fao.org/3/x0490e/x0490e00.htm)
crop water use · [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop) ·
[FAO GAEZ v4](https://gaez.fao.org/) · Romanian crop technology guides (INCDA Fundulea).
Planned: SMAP, SRTM, NEX-GDDP-CMIP6, Sentinel-2.

## Working together

Dependencies are locked in `pnpm-lock.yaml` and `services/engine/uv.lock`.
Install uv: https://docs.astral.sh/uv/getting-started/installation/ .

## Backend P5

The local entry point with request limits is `http://localhost:8080` when running
the full Compose stack. Public cache cleanup is automatic. Integration checks and the
HTTPS profile are documented in [infra/README.md](infra/README.md); future deployment
configuration is in [infra/aws/README.md](infra/aws/README.md). The prepared workflow in
`.github/workflows/checks.yml` runs after the changes are published to GitHub.


Project documentation, code comments, interface text, and generated explanations use
English. Geographic proper names and intentional language-detection test samples retain
their original spelling. See `AGENTS.md` for the language policy.
