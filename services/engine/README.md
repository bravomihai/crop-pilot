# Python engine — P2/P3/P4

One FastAPI service contains three modules. The browser communicates with Next.js,
which forwards requests to Python using an internal token. Farmers do not have
accounts, and the engine does not persist requests.

- P2: `fieldshift/data_service` — POWER adapter and public-data cache.
- P3: `fieldshift/evaluator` — rules, calendar, and evaluation independent of farmer weights.
- P4: `fieldshift/recommender` — generation, comparison, weights, and explanations.
- Integration: `fieldshift/pipeline.py` and `fieldshift/api.py`.
- Fictional demo: `fieldshift/demo.py`; never use its calendar function in the real engine.

`ENGINE_MODE=computed` (the default in `.env.example`, with `ENABLE_NASA_POWER=true`) runs the
real engine; `demo` returns clearly labelled examples. `computed` requires the real
data and evaluation modules and returns 503 when they are unavailable; there is no
automatic fallback to demo. No yield or profit forecast is implemented. The POWER
adapter requires separate live verification; see `docs/status.md` for recorded checks.

Reproducible setup from the root: `uv sync --project services/engine --frozen --extra dev`.
The reference uv version is 0.9.5; dependencies are locked in `uv.lock`.
Schemas live in `packages/contracts/schemas`; export them from the workspace when changing the contract.

See the root README for startup commands. Do not start services for a task limited
to static checks. Unit tests do not require NASA, PostgreSQL, or an HTTP server.
Comments, errors, explanations, and display crop names use English. Intentional
non-English language-detection samples remain in the regression tests.
