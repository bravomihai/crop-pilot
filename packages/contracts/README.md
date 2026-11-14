# Shared contracts

`src/index.ts` is the Zod/TypeScript source. `pnpm contracts:generate` exports the JSON
Schemas consumed by Python; commit the generated schemas. The JSON examples are
fictional and allow independent frontend development. Do not copy types by hand into the web app.

Requests contain no user_id, farm_id, email, phone number, or field geometry. Results
contain up to three plans, each with three main crops and calendar windows.
The example is for development only. See `docs/api.md` and `AGENTS.md`.

Any structural change must include the Zod source, regenerated schemas, examples,
and consumers in the same PR. In addition to JSON Schema, `validateResultSemantics`
checks relationships between fields, including ordering, sources, and plan count/status.
Use English for descriptions and example display text; keep contract keys and IDs stable.
