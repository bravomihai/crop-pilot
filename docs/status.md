# Implementation status

This file includes historical verification records. Later entries describe newer
runtime and interface states; earlier checks are not new claims of scientific validation.

## Written in the repository

- pnpm workspace: one Next.js application for interface/backend and one Python service.
- Zod contract and generated JSON Schemas; requests/results contain no user entities.
- Form with locality/point, availability date, optional history/soil, and priorities.
- Leaflet/OpenStreetMap, Open-Meteo/GeoNames search, and three cards with calendars.
- Frontend adapter for independent development and visibly labelled demo mode.
- Stateless Next.js endpoint with validation, timeout, and result checks.
- Prisma/PostgreSQL for optional public-data caching, with an initial migration.
- Internal Python API, pipeline, and P2/P3/P4 interfaces.
- NASA POWER daily-data adapter; not checked live during the rebuild.
- Demo generator respecting chronological order and exclusions, without fabricated scores.
- Compose configuration, AWS instructions, and an initially inactive CI reference.
- P4 (branch `alexia`): deterministic recommendation engine in `recommender/` with
  bounded sequence generation from P3 rules; feasible/infeasible/unknown classification;
  calendar checks (including autumn crops and `available_from`); normalized weights;
  intervals for missing scores; Pareto analysis; diverse selection with disclosed
  trade-offs; scenario/reference-climate comparison when confirmed by P3; explanations
  and qualitative confidence derived from evidence. Integrated in `pipeline.py` without
  fallback. P4 user-facing output is English. Adapted to the extended `main` contract:
  optional `productivity`; `current_rotation` → P3-evaluated `baseline` (with `violations`,
  omitted with an explanation when P3 supplies no calendar/sources); `history[].source`
  used in confidence and `local_checks`; `plan.scores` with `null` for unknown.
  Climate-scenario comparison uses the reference climate, separate from the current rotation.
  `pipeline.py` again calls `recommend_rotations`, so P5 `tests/test_api.py` passes.
  P3–P4 integration was checked with real modules (`load_rules`, `evaluate`, pipeline)
  and the historical NASA POWER fixture (Bărăgan, 2005–2025) in place of P2: 23 tests
  in `test_p3_p4_integration.py` cover the contract, feasibility, unchanged P3 scores,
  priorities, scenario vs. reference climate, a current rotation with violations,
  exclusions/history, uncovered zones, missing data, and repeatability.
  A cold complete request takes about 14–16 seconds, around 18% of the 90-second
  `ENGINE_TIMEOUT_MS`; P3 replay accounts for over 98% of the time. Tests found five
  P4 bugs that were fixed: a scenario disabled by an unknown crop in the current
  rotation; lost P3 reasons outside coverage and for empty results; unpropagated P3
  assumptions; and below-median wording when displayed values were equal.
  Python suite: 162 passed, 0 failed (2026-11-14). This is not agronomic validation;
  HTTP `computed` remains 503 until P2 is ready. pnpm was not run in that verification
  because `node_modules` was absent; contracts were unchanged.
  Details: [P4_IMPLEMENTATION_REPORT.md](P4_IMPLEMENTATION_REPORT.md).

## Remaining team work

- P2: live POWER verification, indicators and quality checks, and justified integration of other sources.
- P3: cited regional rules, thresholds, water balance, compatibility, and validated calendars.
- P3/P4: agree on the intermediate evaluation contract proposed in the P4 report:
  0–1 `criteria` with provenance (including `productivity`), `calendar`, `scenario_applied`,
  `sources`, and `local_checks`. Infeasible sequences also need calendars and sources
  so the current rotation can be displayed with its violations.
- P4: integration check with the real P3 evaluator (Fundulea), selection-threshold
  calibration, and crop families for diversity. `computed` remains 503 until P2/P3 are ready.
- P1: UX/accessibility refinement, comparisons, and source-detail presentation.
- P5: actual AWS deployment and real secret configuration at deployment; local preparation is described below.

## Intentionally outside this version

Accounts, email/login, persistent sessions, farmer profiles, saved analyses, SMS,
WhatsApp, field outlines, precise yield/profit predictions, trained ML, and CMIP6.

## Initial verification limits (historical)

The user asked not to check application startup. Next.js, FastAPI, Docker, PostgreSQL,
and migrations were not started, and no deployment was performed. Static and contract
checks do not validate external services or agronomic evaluation.

Verified during the rebuild: JSON Schema and Prisma client generation, web/contracts
TypeScript checks, Python syntax, and four local contract/calendar checks. Node and
Python lockfiles were generated. No startup or deployment was performed.

CI was retained as an example in `infra/ci/checks.yml.example`. The available GitHub
token could not publish workflows. To activate it, move the file to
`.github/workflows/checks.yml` using access that permits workflow administration.

## P5 verification — 2026-11-14

- Implemented `GET /api/engine/status`: engine HTTP connection, mode and contract,
  3-second timeout, errors without URL/token, and no cache. It does not certify agronomy.
- `pnpm test:backend`: 18 tests passed for success, configuration, incompatible
  responses, timeouts including body reading, and absence of secret information.
- Schemas and Prisma client generated; TypeScript and Next.js build passed.
- The four existing Python tests passed with locked dependencies.
- Checked real local Next.js/FastAPI processes in `demo` with cache disabled:
  status 200; recommendations 200 with three plans of three crops each and the requested
  location; invalid form 400; direct unauthenticated engine/internal-cache access 401;
  after stopping the engine, the new status endpoint returned 502.
- Local configuration was ignored by Git and used a generated shared token. Processes
  started for verification were stopped. No PostgreSQL, Docker, migrations, or deployment.
- Live NASA, PostgreSQL operation, and `computed` agronomy were not checked.
  The CI example included backend tests but remained inactive.

## Consolidated P5 backend — 2026-11-14

### Implemented and checked locally

- Recommendations: bounded JSON/body size, validated configuration, 504 timeout
  including body reading; incompatible responses and those violating exclusions or
  availability are rejected. No redirects or computed → demo fallback.
- Geocoding: provider/cache validation, checked coordinates, bounded response, and
  distinct connection/data/timeout errors. Open-Meteo was checked live.
- All implemented endpoints: `no-store`, `X-Request-ID`, and structured logs with
  operation, status, code, and duration; no forms/tokens/URLs in these logs.
- PostgreSQL 17 in Docker: migration applied; writes, reads, upserts, expiration, and
  cleanup checked. Authenticated internal DELETE removes at most 1000 entries per batch.
  Periodic service runs at startup and hourly. Database deadlines are 1 second.
- Database temporarily stopped: cache failures were controlled while geocoding and
  demo calculation continued. The database and engine were restored after checks.
- Real NGINX gateway: 413 for oversized bodies, 429 with Retry-After for rate limits,
  and blocked public access to the internal API. NGINX/Caddy configuration checks passed.
- Web/migration/engine images built; Compose started and checked over HTTP.
  The protected local app was available at `http://localhost:8080`.
- 60 backend tests and 12 Python tests passed; separate PostgreSQL test passed.
  This includes a real HTTP stalled-body timeout, not just a simulated exception.
  TypeScript and build passed. CloudFormation validated with cfn-lint 1.60.1.

### Prepared for deployment, without cloud execution

- `.github/workflows/checks.yml` includes types, contracts, tests, real PostgreSQL,
  Docker builds, ingress configuration, and CloudFormation lint. It runs on pushes/PRs;
  it was not published or executed on GitHub during that task.
- Production HTTPS through Caddy, direct service ports removed, and rotating logs.
  Certificate issuance/public access were not tested: no domain/deployment was selected.
- AWS: EC2 + IAM/SSM template, access rules, encrypted disk, and SecureString loading
  into ignored `.env.production`. Documentation: `infra/aws/README.md`.
  Configuration is prepared; no AWS resources or production secrets were created.

### Team dependencies and limits

- Successful computed-mode tests explicitly use simulated modules and check only
  contract/orchestration for 0/1/2/3 plans. They are not real agronomic evaluation.
- With the real modules available at that time, Next.js → Python computed mode was
  checked and returned 503 without fallback. P2/P3/P4 must deliver and validate models/data.
- NASA POWER was not checked live in that task. No AWS monitoring or alerts exist;
  implemented diagnostics are local logs.
- P5 work is on `mihail`. Environment files/local secrets are ignored by Git.
  Local containers were left running for review.

## Verificare P2 live — 2026-11-14

- NASA POWER: datele din 2025 au 365 de înregistrări și 12 rezumate lunare, fără zile
  lipsă pentru temperatură sau precipitații, în Fundulea, Dobrogea și Slobozia.
- SoilGrids: profilul ponderat 0–30 cm a furnizat textură, pH, carbon organic și AWC
  estimate la Fundulea și Dobrogea. La Slobozia nu au fost disponibile valori.
- Fluxul complet `computed` la Fundulea a folosit 20 de ani, a produs trei planuri și
  baseline, iar răspunsul a trecut validarea contractului.
- Testele motorului după integrarea P2: 160 trecute. Agregarea pe contur rămâne
  neimplementată; rezultatele SoilGrids sunt estimări, nu analize de teren.

## P2 terrain — country-wide point support

- The OpenTopoData public `srtm30m` endpoint was checked at eight Romanian locations
  spanning western, eastern, northern, southern, central and coastal regions. All returned
  SRTM elevations. The dataset covers 60°S–60°N, so its coverage includes Romania.
- The engine requests one 3×3 neighborhood around each submitted point, calculates a
  Horn slope estimate in percent, caches the response, and passes `static.slope_pct` to
  the existing erosion component. It does not calculate parcel-wide slope from a polygon.
- OpenTopoData receives the point coordinates. Its published public API limits are
  1 request/second and 1000 requests/day; this is suitable for a prototype, not a
  confirmed production-scale service.

## Frontend

The English dashboard retains its explicit demo indicators, local-only PDFs, and
five preview-priority sliders. The full `/calculator` now supports optional current
rotation, history sources, productivity priority, baseline/score comparison,
local checks, shared crop timelines, and cancellable scenario recalculation.
Both maps have capability-derived GIBS context, POWER-cell and rule-zone outlines.
Replay and climate-trend charts are preview-only, waiting for future fields.
TypeScript, 82 backend/data checks, 25 UI checks, and mock production build passed;
Edge checks covered fixtures, 375/1440 px, keyboard interactions, light/dark, and
tile failure isolation. No scientific or physical-touchscreen validation is
claimed. See docs/frontend.md for exact identifiers, previews, and verification.

## Single-page map interface — 2026-11-14

The main page is now a full-screen map with location search and one draggable
field point. No polygon is required. A compact deep-green planning panel contains
the date, previous crop, soil type, irrigation, and planning focus, followed by
Calculate. Rotation, exclusions, soil pH, history source, and a hypothetical
climate scenario remain under More options. All selections use the shared request
contract and existing recommendation hook; no illustrative crop ranking is sent
as real analysis. Results and errors open over the same map. The old calculator
and chart-preview routes redirect to `/`.

Removed from the main interface: workspace sidebar, fictional KPI cards,
compatibility previews, PDF placeholders, and coming-soon voice controls.
NASA overlays are optional and load only when opened.

Verified: web TypeScript, 26 existing/updated UI checks, successful main-page HTTP
response, redirects, desktop and narrow-phone browser layouts, live location
search, direct point selection, retained form entries, and optional controls.
Calculate reaches the existing API but returns `engine_not_configured`: the local
web app has no configured engine credentials, and no engine responds on port
8000. No planner service, database, migration, or deployment was started, and no
successful agronomic computation is claimed.

## Local calculator restored and zoom capped — 2026-11-14

Installed the locked Python runtime dependencies and created matching, ignored
local web/engine configuration with a generated service token. The engine now
runs locally on 127.0.0.1:8000 in explicit demo mode; the web uses the real local
API, with frontend fixture mode disabled and no database required. A synthetic
request through Next.js returned HTTP 200, three demo plans with three crops each,
the submitted location, and calendars respecting the start date. Browser Calculate
also displayed three plans. These are fictional integration examples; scientific
computed-mode evaluation remains unfinished.

The point map and its base layers now stop at zoom 17, avoiding the unavailable
imagery levels reported by the user. Browser checks confirmed real imagery at the
limit, disabled zoom-in, and no further zoom through the keyboard. TypeScript
passed. No tracked secrets or backend/scientific logic were changed.

## Interface palette — 2026-11-14

Restricted the map interface to black, dark green (#123c2f), and white, with
neutral transparency for secondary text and borders. Removed cream, pale-green,
and blue UI accents from forms, badges, notices, sliders, map controls, and
focus states. Existing chart-series colours on the demo rotation rows and
satellite imagery are preserved. Browser checks confirmed the form, calculation
results, and computed control colours; no recommendation behaviour changed.

## English-language normalization — 2026-11-14

Translated AGENTS.md, the remaining Romanian documentation, and historical status
records into English. Added an English-only policy for project text, with explicit
exceptions for geographic proper names, original source titles, and intentional
language-detection test samples. Kept public contract keys, crop IDs, commands,
and previous interface changes intact. Removed unused Romanian crop-name aliases;
the existing English `name` values remain authoritative.

Geocoding now requests English provider labels and uses language-specific cache keys,
so earlier Romanian responses are not reused. Updated the provider-language regression
check. Verified: contracts/web TypeScript, 82 backend/data checks, 51 focused Python
checks (evaluator, English output, and contracts), and whitespace validation.
