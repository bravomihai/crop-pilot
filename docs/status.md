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
- P4: deterministic recommendation engine in `recommender/`. It generates sequences from
  P3's rules, classifies them as feasible/infeasible/unknown, checks calendars, applies
  normalized priority weights with intervals for missing scores, runs Pareto analysis,
  selects diverse plans with disclosed trade-offs, compares a scenario against the
  reference climate, and writes explanations and a qualitative confidence grade from the
  evidence. It evaluates `current_rotation` as `baseline` (violations are agronomic rules
  only; the farmer's own exclusions are reported separately) and caps confidence at "low"
  on provisional rules. Integration with real P2 data, P3 and the web app is covered by
  `test_p3_p4_integration.py`, `test_p4_web_integration.py` and
  `test_app_audit_fixes.py`. This is not agronomic validation.
  Details: [P4_IMPLEMENTATION_REPORT.md](P4_IMPLEMENTATION_REPORT.md).

## Remaining team work

- All: one live end-to-end check in a browser with real servers in computed mode before
  the demo, using fields warmed into the local cache (`python -m fieldshift.warm`).
- P1: remove the unused earlier dashboard and calculator components once the `maria`
  branch is settled; optionally display `monthly_climate`.
- P2: review the `maria` branch (Romania-wide crop rules, field sampling) with P3 and P4
  before merging; it lowers P4's search limit to 500 sequences, which should be a
  test-only setting instead.
- P3: agronomist review of the southern rules and the provisional thermal-band shifts;
  high-altitude and wetland sites are only disclosed, not excluded.
- P5: VPS deployment and real secrets; confirm the GitHub workflow passes. The Python
  engine keeps computing after a cancelled request (no cooperative cancellation).

## Intentionally outside this version

Accounts, email/login, persistent sessions, farmer profiles, saved analyses, SMS,
WhatsApp, drawing a field outline in the interface (the contract's optional
`field_boundary` is accepted by the engine), precise yield/profit predictions, trained
ML, and CMIP6.

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
  into ignored `.env.production`. This historical scaffold was removed when switching to the VPS setup; see `infra/vps.md`.
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

## Whole-application audit and fixes — 2026-11-14

Integrated `origin/demo-improvements` (Tudor) into local `alexia`; `origin/maria` is not
merged yet (see Remaining team work). Fixed:

- Result data gaps no longer copy every evaluated sequence's gaps (up to 15 near-identical
  winterkill lines); P3 writes one winterkill note per crop.
- A past availability date plans from today and says so, instead of producing plans in
  the past; the date field cannot go before today; harvest year cannot be in the future.
- Inputs without effect (irrigation limit with irrigation off, unapplied or conflicting
  crop shortlist) are reported; high elevation (> 800 m) is disclosed.
- The current rotation's `violations` are agronomic rules only (exclusions reported apart).
- NASA POWER, SoilGrids and SRTM are fetched in parallel under `DATA_DEADLINE_S` (60 s);
  late soil/slope become data gaps, a late POWER answer fails the request.
- The engine's 422 reason (outside Romania, invalid outline) reaches the farmer.
- Results show past-season replay and observed yearly climate (rainfall, temperature,
  hot days); the form's scenario steps match the what-if and follow a recalculation.
- CI now runs the UI tests. `docs/frontend.md` and `docs/api.md` describe the current app.

Verified: Python 223 passed; web TypeScript, backend 87/87, UI 30/30, production build.
**Live** (real NASA POWER, SoilGrids, SRTM; temporary local engine in computed mode and
the built web app; Next.js `/api/recommendations`): Fundulea 8.1 s, complete with
baseline, 17 replayed seasons and 20 climate years; the same field with +2 °C / −20 %
rain 6.6 s; Suceava 10.0 s on provisional rules with low confidence; Budapest 422.
In the browser, the demo link, Calculate, the new charts and a +2 °C what-if worked, and
the form followed the what-if scenario. Not verified: Docker, NGINX, PostgreSQL cache,
AWS, the GitHub workflow, screen readers and touch devices. Not agronomic validation.

## Integration of `demo-improvements` up to `e5b8391` — 2026-11-14

Merged Tudor's crop-check rules (`b614bf1`), past-season replay and climate charts
(`17c910f`), glossary (`e566a58`), and AI summary with print sheet (`e5b8391`) into
local `alexia`, on top of the audit fixes. The duplicate replay/climate section from the
audit was dropped in favour of Tudor's `results-evidence.tsx`; its replay note now says
when a hypothetical scenario was applied. Fixed for the AI summary: the gateway's 32 KB
body limit would have rejected every summary request (results are 100+ KB), so
`/api/summary` gets a 256 KB limit and its own rate limit (6/min per IP), and the page
sends a trimmed, contract-valid result; switching language cancels a pending summary;
an empty summary section is not printed.

Verified: Python 227 passed; web backend 95/95, UI 32/32, TypeScript, schemas unchanged,
production build. **Live** (real NASA POWER, SoilGrids, SRTM; temporary local computed
engine and built web app, in a browser): Fundulea with previous crop, current rotation
maize → winter wheat, water focus (36 % weight) and pea avoided produced three plans
without pea and the current-rotation baseline; replay (2007–2023) and climate
(2006–2025) charts show computed data; a +2 °C what-if updated the replay note and the
form; the AI summary showed "not set up" (no key configured) with the plans still
usable; Romanian labels display with diacritics; print rules keep only the results.
**Not verified live:** an actual AI summary (no `ANTHROPIC_API_KEY`; covered by tests
with a mocked client), NGINX/Caddy limits (configuration only), Docker and AWS.

## Bare soil before the first crop and printed inputs — 2026-11-15

- P3's soil score now counts the time from the field availability date to the first
  sowing as bare soil (`scoring.soil_index`, `initial_bare_days`); before, only gaps
  between crops counted, so a plan waiting about ten months for its first crop looked as
  well covered as one starting at once. The soil summary mentions a wait of two months or
  more, and the cover-crop check covers it. Weights and thresholds are unchanged and still
  await agronomist review; P3 (Tudor) should confirm the change.
- The rotation calendar shows that wait as a hatched bare-soil gap.
- The printed sheet starts with "What was entered": field point, availability date,
  previous crop, current rotation, soil, irrigation, priorities, avoided crops, scenario
  and calculation reference. It is hidden on screen.
- The P4 report no longer says computed mode is unavailable over HTTP.

## Survival Mode — 2026-11-15

"Challenge my plan" in the results opens Survival Mode (`docs/survival-mode.md`): the
worst drought, heat and erratic-rain years are picked from observed `climate_context`,
and every rotation is compared on the same replayed season, using P3's existing replay
scores and per-crop evidence. No new agronomic calculation; no AI model involved.

- **Contract:** optional `plan.replay[].field_free_from` (historical start date of each
  replay), written by P3 (`evaluator/core.py`), checked and forwarded by P4
  (`recommender/evaluation.py`), schema regenerated, full example updated. Older results
  stay valid; the frontend then derives the alignment and says so.
- **Automated checks (all passing):** Python 230 passed (2 new in
  `test_replay_climate.py`); web `test:backend` 115/115 (19 new in
  `tests/survival.test.ts`: season selection, same-start comparison, determinism and
  ties, unknown scores, no baseline, one plan, missing data, different replay periods,
  score differences, uncertainty notes, scenario vs observed, demo, moved request date);
  `test:ui` 37/37 (4 new: button, accessible panel, unavailable challenge, reveal);
  TypeScript; contract generation reproduces the committed schema; production build.
- **Live check (computed mode, NASA POWER):** engine and Next.js started locally;
  Fundulea (Călărași), previous crop maize, current rotation maize → winter wheat,
  loamy, rain-fed. Status `complete`, 3 plans plus the current rotation, climate record
  2006–2025, 16 seasons shared by every rotation. In the browser: drought **2022**
  (ET₀ 1117 − rain 425 = 692 mm deficit; water scores current 66, Plan 1 68, Plan 2 64,
  Plan 3 50), heat **2012** (60 days above 32 °C; record maximum 2024 disclosed as not
  replayable for every rotation), erratic rain **2016** (19-day dry spell, 6 heavy-rain
  days). Each value was compared with the raw API response in the page. Decision flow
  tested with mouse and keyboard (Plan 3: −16 points; Plan 1: +2 points). With **+2 °C**
  the same observed years and evidence remained, the scores changed to the scenario
  values (drought: 58 / 64 / 65 / 61) and the panel labelled them scenario-adjusted.
  Mobile (375 px): one-column cards, no horizontal overflow.
- **Not verified:** screen-reader software (markup checked by tests: labelled radio
  group, `aria-pressed`, bar text alternatives, live region); other Romanian locations;
  Docker/AWS deployment.

## SVG extension hydration compatibility — 2026-11-15

The shared dashboard Icon component now suppresses hydration attribute warnings
on its SVG element, where Dark Reader injects inline stroke attributes before
React hydrates. The existing root HTML exception does not cover nested icons.
The exception is local to the icon element; its path remains normally checked.

Verified: contracts/web TypeScript, all 27 existing UI checks, and whitespace
validation. A browser reload with Dark Reader enabled was not verified.

## CropPilot, root configuration and VPS hosting — 2026-11-15

Renamed product branding, workspace packages, service health labels, and deployment
names to CropPilot. The Python module directory remains `fieldshift` for internal
imports. The repository remote is now `git@github.com:bravomihai/crop-pilot.git`.

Docker Compose and native web/engine/Prisma commands now share a single ignored root
`.env`. This checkout has generated local credentials; `.env.example` contains only
placeholders for new checkouts. Per-service environment files/templates were removed.
Real mode is enabled (`ENGINE_MODE=computed`, `ENABLE_NASA_POWER=true`, frontend fixtures
disabled). The website already forwards validated calculations to Python with the
shared server-side token. AWS provisioning was removed; `infra/vps.md` documents the
existing HTTPS Compose profile for a user-managed server. The connectivity helper is
now read-only and does not stop services or switch the engine to demonstration mode.

Replaced Anthropic with OpenAI Responses for English-only summaries. The configurable
default is `gpt-6-luna`; the key belongs in root `OPENAI_API_KEY` and is not required
for calculated recommendations. The UI language selector was removed, non-English
summary requests are rejected, and existing numeric checks are retained. Incomplete,
refused, timed-out or failed summaries leave the original calculated plans available.
Response storage is disabled for the OpenAI request.

Verified: production build, contracts/web TypeScript, 33 UI checks, 97 backend checks,
3 configuration-loader checks, 26 focused Python checks, Python syntax, contract schema
regeneration without changes, and local/production Compose configuration. Checked
that web and engine receive the same generated token and production exposes only
HTTPS ingress. UI testing, a live OpenAI call, Docker startup/migrations and VPS
deployment are left to the user. No paid API call or deployment was performed.

## Shared NGINX VPS and CI/CD — 2026-11-15

Prepared a single production checkout at /home/ubuntu/crop-pilot, a dedicated
croppilot-deploy account/key, main-only production environment, and host NGINX
HTTPS. Removed the earlier unshipped release-directory/privileged-receiver
approach. The VPS Compose profile publishes only 127.0.0.1:18080 and leaves
production migrations manual. The Actions deployment requires successful CI,
main, and both original/rerun actors to be bravomihai. It fast-forwards only to
the exact tested main SHA, preserves local settings, refuses dirty/stale
checkouts and pending migrations, and verifies container/HTTPS health.

Verified locally: 227 Python tests, 97 backend tests, 33 UI tests, 3 configuration
checks, TypeScript and production build; 5 isolated deployment regression tests;
ShellCheck, actionlint, VPS Compose isolation/manual-migration dependency, and
NGINX syntax. Verified dedicated-key SSH, Docker access, certificate issuance
and the existing certificate-renewal timer on the VPS. GitHub CI passed on PR #13
and its main merge, 63afbd3. The first installation applied the initial cache
migration explicitly, outside automatic CD, and started all five CropPilot
services. Only the gateway is published, on 127.0.0.1:18080; the existing
Universident database remains healthy.

Verified live over HTTPS: expected commit, homepage and browser JavaScript,
location search, invalid input rejected with 400, internal cache blocked with
404, and computed-engine reachability. The public Fundulea example returned
HTTP 200 in 11.3 seconds, complete with three plans of three crops each; its
response passed the shared JSON schema. The CI SSH script also passed its
read-only verification against the real server. This checks deployment and
integration, not agronomic validity. No paid AI request was made; the optional
OpenAI key remains unset on the server.

Normal updates explicitly pull gateway/maintenance images before replacement,
without pulling or replacing PostgreSQL. Automatic deployment was enabled after
the initial installation checks; the next main merge exercises that path.


### Docker 29 image verification

The first push-triggered deployment built and updated the application to main
commit 1fc2933, but the final image check falsely rejected the unchanged engine.
Docker's running container referenced its platform manifest/config while the
default image lookup returned an OCI index with build attestations. Verified
on the real VPS that the engine's platform manifest exactly matched the newly
built engine image and that public HTTPS served the expected web commit.

Deployment verification now compares platform manifests using API 1.49+.
Six deployment regression tests include distinct legacy config/index/platform
IDs and a negative case that still rejects a genuinely stale running image.
The remaining main/actor, migration and health gates are unchanged.

## Easier-to-read results — 2026-11-15 (branch `tudor`)

The results panel now opens with an **At a glance** card built from the result itself,
without AI. It shows:
- the best plan and its first sowing window;
- the score comparison with the current rotation;
- the main risks and the checks to do before deciding;
- one line for each other plan;
- the missing data a farmer can act on.

Plan cards show the crops, dates, scores and one sentence. Benefits, trade-offs, the
reason for each crop and the local checks are under "Why this plan?". Assumptions,
all missing data and sources are collapsed under "How this was calculated". "Back to
summary" links close the long sections. The results panel has a full-screen toggle,
and Escape exits it.

Engine text fixes:
- the ET₀ wording is fixed;
- the duplicate score, weather and ET₀ lines are removed;
- the replay is described in one line;
- the winterkill notes are merged into one line;
- the soil note says when regional SoilGrids estimates were used.

Unexpected engine failures are logged by error type before the 502; exception
messages and tracebacks are omitted because provider URLs can contain field coordinates.
Slobozia/Fundulea were removed from tracked files: the INCDA source lost its place name
and URL, and the examples use a neutral name.

Verified: Python 231 passed; web backend 97/97, UI 35/35, TypeScript; schemas unchanged.
**Live** (real NASA POWER, SoilGrids, SRTM from the local cache; engine via
`pnpm dev:engine`, web via `pnpm dev`, in a browser): a computed result with the current
rotation maize → winter wheat showed the summary, collapsed details and full screen
correctly. Known on Windows only: `scripts/env.test.mjs` expects `/` path separators
and fails 1 of 3 checks; the uvicorn `--reload` supervisor can crash on file changes.

### Integration review with current VPS deployment

Preserved the current CI/CD and deployment records while merging Tudor's
commits. Replaced exception tracebacks with error-type-only logging because
provider URLs can include field coordinates or credentials, and added an HTTP
regression test proving those values do not reach logs or error responses.
Cancelled summary responses are ignored.

Verified: 232 Python tests, 97 backend tests, 35 UI tests, 3 configuration
checks, TypeScript, unchanged generated schemas, and a production build.
Browser checks with an explicitly local demo engine covered the At a glance
card, collapsed details, full-screen toggle, return navigation and Escape;
paid AI and NASA calls were disabled for that UI check. No scientific
validation is implied.

The CI/CD correction was independently verified by the successful automatic
main run 43700477811 and live HTTPS at commit d7f5eea: a real example request
returned three computed plans of three crops each and passed the shared schema.


## VPS engine permissions and CI triggers — 2026-11-15

Main run 43702564664 passed application checks but failed the deployment health
gate: new Python files inherited restrictive VPS checkout ACLs. Docker copied
their root-owned permissions into the image, so the non-root engine could not
read `fieldshift/api.py`. The service was restored by adding read/traverse
permissions to public source inside the engine image; host secrets were unchanged.
The recovered engine, web, gateway and maintenance services passed Compose
health checks and the local computed-engine connectivity check.

The engine Dockerfile now normalizes public source permissions before installing
the package. Its existing CI build also verifies a non-root import with a
restricted source file, without network access. CI runs on PRs and `main` pushes;
feature branch pushes no longer create duplicate PR/push runs. Production health
checks and the owner-only deployment gate remain required.


Verified locally: the image built from a restricted source file imports the API
as UID 1001 with networking disabled; workflow lint and six deployment guard
tests pass. Public HTTPS serves revision 76c4c58 and reports the recovered engine
as reachable in computed mode. The full GitHub suite and automatic deployment
will verify the permanent change after merge.


### Survival Mode integration with current production

Integrated PR #17 on the maintainer branch without altering the contributor's
branch. Its historical replay field, interface and tests merge cleanly with
the current main. Retained the image permission fix, PR/main-only CI triggers,
privacy-safe engine logs and owner-only deployment restrictions.

Verified locally: 118 backend tests, 40 UI tests, 3 configuration checks,
TypeScript and regenerated schemas matching the committed contract. Full Python,
database, build and container checks run in GitHub before merge. No agronomic
validation is implied.

## System theme and interface consistency — 2026-11-15

The map workspace now follows the operating system's light/dark appearance without
a theme selector or saved preference. Shared tokens use white, black and forest
green; planner, results and NASA layer panels have consistent card corners,
borders, form controls, selection states and keyboard focus indicators. CropPilot
branding sits at the top right of the map and results header.

Removed the Prototype badge, project-info button/dialog, Back to summary links,
plan-count badge and missing-rotation prompt when no rotation was supplied. A
supplied rotation that cannot be evaluated still produces its existing warning.
Heading focus remains available to assistive technology without a visible box.
The map is limited to zoom levels 6–17, with non-wrapping basemaps and world bounds.

Verified: both workspace TypeScript checks, all 40 UI tests, the production web
build and `git diff --check`. The separate preview server started successfully.
Visual browser checks could not be completed: the in-app browser initialization
timed out, and native browser access stopped because the automation tool could not
confidently determine its current URL. Responsive appearance, live system-theme
changes and runtime map interaction therefore remain visually unverified. No
scientific validation or deployment is implied.
