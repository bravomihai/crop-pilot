# Python engine

The active engine implementation, dependencies, and tests are in [`services/engine`](../services/engine/README.md). This directory is retained for legacy work and is not a standalone Python project; do not run `pytest` from here.

## Run engine tests

From the repository root, synchronize the pinned development dependencies and run the canonical engine test suite:

The legacy `engine/fieldshift/data` module fetches NASA POWER and SoilGrids data and
calculates reference ET₀, but its `FieldData`/`quality` shape is not used by the active
recommendation pipeline. New data integrations belong in `services/engine`; its response
uses titled `sources` and top-level `data_gaps`.

```sh
uv sync --project services/engine --frozen --extra dev
uv run --project services/engine --frozen --extra dev python -m pytest services/engine/tests
```

See the [repository README](../README.md) for setup and the [engine README](../services/engine/README.md) for the current engine architecture and limitations.
