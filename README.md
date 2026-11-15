# CropPilot: crop rotation planning with NASA data

NASA Space Apps Challenge 2026 · **Field Shift: Adapting Farms with NASA Data**

Farmers in Romania choose the next crops for a field mostly from habit and last year's
prices, while summers get hotter and dry spells longer. CropPilot helps them compare
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
- **Survival Mode compares like with like.** "Challenge my plan" picks the field's
  worst observed drought, heat and erratic-rain years and compares every rotation on
  the same replayed season, from P3's own results; it is history, not a forecast
  (`docs/survival-mode.md`).
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

The website is connected to the Python recommendation engine. Computed mode uses
public weather and soil data, regional rules, evaluation and recommendation modules.
Recorded integration checks and their limits are in [docs/status.md](docs/status.md).
The rules and scores still require local agronomic review; passing tests do not
establish scientific accuracy. No yield or profit forecast is implemented: the money shown per plan is a
rough estimate from county statistics, past prices and published costs, not a forecast.

## Repository

| Folder               | What it holds                                                   | Owner  |
| -------------------- | --------------------------------------------------------------- | ------ |
| `apps/web`           | Next.js + React: form, map, results, public API, optional cache | P1, P5 |
| `services/engine`    | Python FastAPI: `data_service`, `evaluator`, `recommender`      | P2–P4  |
| `packages/contracts` | Zod contract, generated JSON Schemas, examples                  | all    |
| `docs`               | Architecture, API, team split, status                           |        |
| `infra`              | VPS deployment and reverse proxy                                | P5     |

Start with [AGENTS.md](AGENTS.md), [docs/team.md](docs/team.md) and [the API](docs/api.md).
The contract lives in [`packages/contracts/src/index.ts`](packages/contracts/src/index.ts);
[`recommendation-request.full.json`](packages/contracts/examples/recommendation-request.full.json)
and [`recommendation-result.full.json`](packages/contracts/examples/recommendation-result.full.json)
show every optional field.

## Configuration and startup

Use one `.env` file at the repository root. For a new checkout, copy `.env.example`
to `.env` and replace the password and internal token. This checkout already has
private, generated local credentials. Do not put keys in browser code or commit `.env`.

### Full app with Docker

Stop any native web server already using port 3000, then run from the repository root:

```sh
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
```

Open http://localhost:8080 and use a real Romanian field in the UI.
The website already sends Calculate requests to the engine; Compose supplies the
internal URLs and shares the token automatically. Defaults are real computation
(`ENGINE_MODE=computed`, `ENABLE_NASA_POWER=true`, `NEXT_PUBLIC_USE_MOCK_API=false`).
The database migration runs automatically before the web container starts.

### Native development

Node 22, pnpm 10.11.0, Python 3.11+ and uv 0.9.5 are required.

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm contracts:generate
pnpm db:generate
uv sync --project services/engine --frozen --extra dev
```

Then run `pnpm dev:engine` and `pnpm dev` in separate terminals, both from the root.
Both commands read the root `.env`. Open http://localhost:3000. No per-service `.env`
files are needed. For the optional PostgreSQL cache, start `docker compose up -d postgres`
and run `pnpm db:deploy`; native commands derive `DATABASE_URL` from `POSTGRES_*`.
Alternatively, use `CACHE_ENABLED=false` to run without a database.

### English AI summary and VPS hosting

Recommendations do not need an AI API key. To enable the optional English-only written
summary, add `OPENAI_API_KEY` to the root `.env`. The default model is `gpt-6-luna`,
configurable with `OPENAI_SUMMARY_MODEL`. It explains the computed plans; it does not
choose crops. Restart native servers after changing `.env`, or recreate the Docker
web service with `docker compose up -d web`.

The shared-VPS deployment at crop-pilot.nemes.engineer uses host NGINX and a single checkout. GitHub Actions setup and manual migration/recovery are documented in [infra/deploy/README.md](infra/deploy/README.md). Standalone Caddy hosting remains documented in [infra/vps.md](infra/vps.md).
The HTTPS profile uses the same root `.env`, plus your domain and certificate email.

## Checks

```sh
pnpm contracts:generate
pnpm db:generate
pnpm typecheck
pnpm test:config
pnpm test:backend
# With local PostgreSQL and DATABASE_URL configured:
pnpm test:cache
services/engine/.venv/bin/python -m pytest services/engine/tests
```

## Data sources

[NASA POWER](https://power.larc.nasa.gov/) daily agro-meteorology ·
[ISRIC SoilGrids](https://soilgrids.org/) · [FAO-56](https://www.fao.org/3/x0490e/x0490e00.htm)
crop water use · [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop) ·
[FAO GAEZ v4](https://gaez.fao.org/) · Romanian crop technology guides (INCDA, the national agricultural research institute).
Planned: SMAP, SRTM, NEX-GDDP-CMIP6, Sentinel-2.

## Working together

Dependencies are locked in `pnpm-lock.yaml` and `services/engine/uv.lock`.
Install uv: https://docs.astral.sh/uv/getting-started/installation/ .

## Backend P5

The local entry point with request limits is `http://localhost:8080` when running
the full Compose stack. Public cache cleanup is automatic. Integration checks and the
HTTPS profile are documented in [infra/README.md](infra/README.md); future deployment
configuration is in [infra/vps.md](infra/vps.md). The prepared workflow in
`.github/workflows/checks.yml` runs after the changes are published to GitHub.


Project documentation, code comments, interface text, and generated explanations use
English. Geographic proper names and intentional language-detection test samples retain
their original spelling. See `AGENTS.md` for the language policy.
