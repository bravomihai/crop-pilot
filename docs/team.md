# Team responsibilities

| Role | Main files | Deliverable |
| --- | --- | --- |
| P1 frontend | `apps/web/src/components`, `src/app/page.tsx`, `globals.css`, `src/lib/api.ts` | Form, locality/point selection, loading state, and three plans |
| P2 data | `services/engine/fieldshift/data_service` | Daily data, units, quality, sources, and public-data cache |
| P3 agronomy | `services/engine/fieldshift/evaluator` | Regional rules, calendar, checks against actual history, and criterion evaluation |
| P4 recommendations | `services/engine/fieldshift/recommender`, `pipeline.py` | Generation and comparison of three plans containing three crops each |
| P5 backend | `apps/web/src/app/api`, `src/lib/server`, `prisma`, `compose.yaml`, `infra` | Validation, Python HTTP integration, Prisma/PostgreSQL cache, and VPS hosting |

## Parallel development

P1 can set `NEXT_PUBLIC_USE_MOCK_API=true` and use the shared example. Do not implement
agronomic formulas in UI components. P2/P3/P4 work in modules with shared data and
exchange functions, not separate servers. P5 keeps the Python service outside the browser.

P2: `build_environment(request) -> dict` with daily data, sources, and gaps.
P3: `load_rules(location) -> dict` and `evaluate(rotation,request,environment,rules) -> dict`.
P4: `recommend_rotations(request,environment,rules,evaluate) -> list[plan]`.
P3/P4 must agree on an intermediate evaluation contract before implementing changes.
The public request/result contract is already shared and checked in both languages.

The first coverage area is the southern and south-eastern plains (Romanian Plain,
Bărăgan, Dobrogea), using the main field crops. The example field in the Romanian Plain
is only a test point. Return `insufficient_data` outside covered zones. An example locality does not
establish agronomic validation.

The new optional contract fields (`current_rotation`/`baseline`, `plan.scores`,
`local_checks`, `history[].source`, `priorities.productivity`) are described in `docs/api.md`.
Existing consumers remain compatible without adopting them immediately. Priorities
and scenarios must affect real evaluation only after the corresponding models are
implemented; demo mode explicitly states that it does not calculate them.

Use English for shared documentation, code comments, interface text, and explanations.
