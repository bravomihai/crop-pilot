# CropPilot contributor guide

## Project

CropPilot compares crop rotations using field location, crop history, soil, irrigation,
and planning priorities. Keep changes focused on the requested feature and use English
for code, comments, documentation, and interface text.

### Code layout

- `apps/web/`: Next.js, React, and TypeScript interface and API routes.
- `apps/web/src/lib/server/`: server-only integrations, engine calls, and caching.
- `services/engine/fieldshift/`: Python/FastAPI data processing, evaluation, and recommendations.
- `packages/contracts/`: shared Zod types, generated JSON Schemas, and API examples.
- `docs/`: feature and architecture details; `infra/` and `compose.yaml`: deployment and local services.

## UI

- Preserve the existing map-based workflow, panel layout, and responsive behavior.
- Reuse existing components and shared styles. Keep the green, black, and white palette,
  light/dark themes, typography, spacing, and controls consistent.
- Keep forms concise; reveal advanced options when needed. Preserve keyboard navigation,
  visible focus, accessible labels, and loading/error states.
- Clearly label demo data, estimates, hypothetical scenarios, and uncertainty.
- For visual changes, check the affected view at desktop and mobile widths in both themes.

## Contracts and data

- Treat `packages/contracts/src/index.ts` as the API source of truth. Import shared
  TypeScript types from `@croppilot/contracts` rather than duplicating them.
- When changing a contract, run `pnpm contracts:generate` and update affected examples,
  producers, consumers, and tests together. Do not hand-edit generated JSON Schemas.
- Use `latitude`/`longitude`, Leaflet's `[lat, lon]` order, ISO `YYYY-MM-DD` dates,
  and explicit units. Preserve missing values rather than replacing them with zero.
- Keep request validation and `request_id` propagation intact. Computed mode must report
  failures explicitly rather than silently substituting demo results.
- Keep the calculator stateless and PostgreSQL caching limited to public data.
  Python accesses that cache through the internal API.
- Keep credentials and server-only integrations out of the browser. Never commit secrets
  or `.env` files.

## Working and verification

- Read the relevant code and feature documentation before making changes. Preserve
  existing work and avoid unrelated refactors.
- Use the versions declared in the repository's runtime files and package manifests.
  Run commands from the repository root.
- Run checks relevant to the change; documentation-only edits do not require app tests.
  Report what was checked and any failures or limitations.
- Local previews may be used to verify changes unless the task restricts them. Production
  deployments and real-database migrations require explicit authorization.
- Work on the current contributor branch and integrate through pull requests. Do not
  overwrite others' changes or force-push without an explicit request.
- Update relevant documentation when behavior or setup changes. Keep historical test
  results and implementation timelines out of this guide.

### Common commands

| Purpose | Command |
| --- | --- |
| Install web dependencies | `pnpm install --frozen-lockfile` |
| Generate contracts | `pnpm contracts:generate` |
| Generate Prisma client | `pnpm db:generate` |
| Type checks | `pnpm typecheck` |
| UI tests | `pnpm --filter @croppilot/web test:ui` |
| Backend tests | `pnpm test:backend` |
| Install engine dependencies | `uv sync --project services/engine --frozen --extra dev` |
| Engine tests | `services/engine/.venv/bin/python -m pytest services/engine/tests` |
