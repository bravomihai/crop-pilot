# Web — P1/P5

Next.js App Router contains both React and the backend endpoints. There is no separate
Vite frontend, cross-application CORS setup, account system, persistent session, or farm storage.

P1 works in `src/components`, `src/app/page.tsx`, `src/app/globals.css`, and `src/lib/api.ts`.
P5 works in `src/app/api`, `src/lib/server`, `prisma`, and deployment configuration.

`NEXT_PUBLIC_USE_MOCK_API=true` enables interface development without Python. Its data
is fictional and labelled. In normal mode, `POST /api/recommendations` forwards the
validated form to the engine and returns the result without saving it.

Web startup and Prisma CLI load the single repository-root `.env` through `scripts/load-env.mjs`.
Inherited container environment values take precedence; no per-app env file is needed.
The schema/migration stores only public cache data. `CACHE_ENABLED=false` disables caching.
Run pnpm commands from the repository root; see the root README and `AGENTS.md`.

The main page contains the complete map-and-planner workflow. Interface text and
location-search display text use English. Geographic proper names retain their spelling.
