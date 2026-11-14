# Python engine

The active engine implementation, dependencies, and tests are in [`services/engine`](../services/engine/README.md). This directory is retained for legacy work and is not a standalone Python project; do not run `pytest` from here.

## Run engine tests

From the repository root, synchronize the pinned development dependencies and run the canonical engine test suite:

```sh
uv sync --project services/engine --frozen --extra dev
uv run --project services/engine --frozen --extra dev python -m pytest services/engine/tests
```

See the [repository README](../README.md) for setup and the [engine README](../services/engine/README.md) for the current engine architecture and limitations.
