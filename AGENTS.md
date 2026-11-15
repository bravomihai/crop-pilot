# CropPilot: instructions for agents and contributors

## Project language

Use English for documentation, instructions, comments, identifiers, interface text,
errors, logs, examples, and generated explanations. Request English display text from
external providers and include the language in cache keys for localized responses.
Keep geographic proper names, source titles quoted in their original language, and
intentional non-English language-detection test cases unchanged. Preserve public API
keys, crop IDs, units, and source identifiers when translating presentation text.

## Current scope — product source of truth

This is an agricultural planning web app without accounts, public authentication,
email, farmer profiles, or persistent anonymous sessions. Each use starts a new form.
Do not add users, saved farms, login, analysis history, or SMS without a new explicit
request. Anveo SMS and direct Meta WhatsApp are possible future extensions, outside
the current version. Do not use Twilio.

Inputs: a locality or WGS84 point, field availability date, crop history when known,
known soil information, irrigation, exclusions, priorities, and an optional hypothetical
scenario. Select a point; do not require a field polygon.

Output: three alternative plans, each containing THREE successive main crops, sowing
and harvest windows, benefits, and trade-offs. The current rotation is optional:
when the farmer supplies `current_rotation`, the result also includes `baseline`,
evaluated like the alternatives for comparison. Optional fields are documented in
`docs/api.md`. Three crops do not automatically mean three years. The plan does not
repeat automatically. Return `limited` or `insufficient_data` when fewer than three
valid alternatives exist; never invent options.

## Interface

Keep the entire workflow on the main page: a full-screen map, location search, one
field point, simple selections, and a Calculate button. Show additional inputs only
when needed. Avoid clutter, placeholder features, and long interface explanations.
Use black, dark green (`#123c2f`), and white for the interface. Preserve the demo chart
row colors and the geographic imagery. Keep demo results visibly labelled as fictional.

## Stack and directories

- `apps/web/`: Next.js App Router, React, and TypeScript; interface and backend in one app.
- `apps/web/src/app/`: page, layout, and Route Handlers.
- `apps/web/src/components/`: planner, Leaflet map, and plan cards.
- `apps/web/src/lib/api.ts`: the single frontend calculation entry point; supports fixtures.
- `apps/web/src/lib/server/`: engine calls, HTTP validation, cache, and Prisma client.
- `apps/web/prisma/`: schema and PostgreSQL migration; Prisma configuration is one level up.
- `services/engine/fieldshift/api.py`: internal Python FastAPI service.
- `services/engine/fieldshift/pipeline.py`: Python module orchestration.
- `services/engine/fieldshift/data_service/`: P2, NASA data and public-data cache.
- `services/engine/fieldshift/evaluator/`: P3, rules and plan evaluation.
- `services/engine/fieldshift/recommender/`: P4, generation, comparison, and explanations.
- `services/engine/fieldshift/demo.py`: fictional integration examples only.
- `services/engine/tests/`: contract and edge-case checks.
- `packages/contracts/src/index.ts`: shared Zod contract and TypeScript types.
- `packages/contracts/schemas/`: GENERATED JSON Schema for Python; do not edit by hand.
- `packages/contracts/examples/`: fictional requests and results for independent development.
- `docs/`: architecture, API, implementation status, and team responsibilities.
- `infra/`: VPS guidance, reverse proxy, deployment configuration, and the CI reference copy
  in `infra/ci/checks.yml.example`.
- `.github/workflows/checks.yml`: backend, contracts, PostgreSQL, and Docker build checks
  prepared for pushes and pull requests.
- `compose.yaml`: local PostgreSQL, migration, engine, and web environment.

## Ownership

P1 owns web components and UX. P5 owns Route Handlers, integration, Prisma, and
infrastructure. P2 owns `data_service`; P3 owns `evaluator` and regional rules; P4 owns
`recommender` and orchestration. P3 calculates criteria independently of weights;
P4 applies priorities and selects plans. Python contributors deliver modules in the
same service; do not build three separate APIs. Discuss contract changes with their
producers and consumers.

## Implementation and verification limits

The repository includes the account-free form, locality search and point selection,
explicit frontend mock mode, API validation, Next.js–Python HTTP integration,
cache schema/migration and internal API, and a NASA POWER adapter retaining daily
values and metadata. P3/P4 implementation and fixture-based checks are documented in
`docs/evaluator.md`, `docs/P4_IMPLEMENTATION_REPORT.md`, and `docs/status.md`.

Do not present implemented code or passing fixtures as scientifically validated
agronomy. Regional rules and model assumptions require local expert review. No
yield or profit forecast is implemented. `computed` must fail explicitly when required
modules or data are unavailable; never fall back automatically to demo results.
The POWER adapter alone does not validate the whole engine. Verify external-service
integration separately. A fixture passing the schema does not prove a working flow.

## Contracts and implementation rules

- Change the Zod source, run `pnpm contracts:generate`, and update examples in the same commit.
- Do not duplicate TypeScript interfaces by hand in the frontend/backend; import `@croppilot/contracts`.
- Coordinates are `latitude`, `longitude`; Leaflet receives `[lat, lon]`.
- Dates use ISO `YYYY-MM-DD`, with explicit units. Unknown does not mean zero.
- Preserve pre-plan history and check transitions/calendars, including autumn crops.
- Separate observations, estimates, and hypothetical scenarios. A scenario is not a forecast.
- Display `mode: demo` visibly. Never present fixtures as real NASA observations.
- Preserve `request_id` from Next.js through the response. Results must match the request.
- Python must not write directly to PostgreSQL; public cache access uses the internal API.
- Do not persist forms, entered histories, soil information, or farmer-associated results.
- `INTERNAL_API_TOKEN` is a service secret, not farmer authentication. Never expose it in the browser.
- The cache is optional; its failure must not prevent calculation or locality search.
- Do not call SMS/WhatsApp services or send messages while testing this repository.

## Commands and checks

Use Node 22, pnpm 10.11.0, Python 3.11+, and uv 0.9.5. Run commands from the repository
root unless stated otherwise: `pnpm install --frozen-lockfile`, `pnpm contracts:generate`,
`pnpm db:generate`, and `pnpm typecheck`.
For Python, run `uv sync --project services/engine --frozen --extra dev`, followed by
`services/engine/.venv/bin/python -m pytest services/engine/tests`.

Do not start servers, Docker, real-database migrations, or deployments without task
authorization. For tasks explicitly limited to static checks, do not start the app.
The initial rebuild had that restriction; later authorized local runtime checks are
recorded separately in `docs/status.md`. Static checks do not establish successful
startup or agronomic validation.

## Git

Do not overwrite `main`. Each contributor works on their own branch and merges through
pull requests; do not push to another contributor's branch.
Do not force-push without an explicit request for that branch. Preserve teammates'
changes. Never commit `.env`, passwords, tokens, cache, or installed dependencies.
Update `docs/status.md` when a component becomes functional, stating exactly what
was verified.
