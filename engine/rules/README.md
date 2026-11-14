# Crop rules (P3)

Agronomic knowledge per region, in the [`CropRules`](../../contracts/schemas/crop-rules.schema.json) format. The evaluator loads `rules/<region>.crop-rules.json` and falls back to the contract example if the file is missing.

Start by copying [`contracts/examples/crop-rules.example.json`](../../contracts/examples/crop-rules.example.json) to `ro-south.crop-rules.json`. Then, for each crop, rule and successor pair:

1. Replace the illustrative value with a real one.
2. Add the real source to `sources` and point to its id (instead of `placeholder_agronomy`).

Validate from the repo root with `python contracts/validate.py engine/rules/ro-south.crop-rules.json`, or run `pytest` in `engine/`.

**Suggested sources:** FAO-56 (Kc, season lengths, root depth), FAO EcoCrop (temperature/rain/pH ranges), GAEZ v4 (attainable yield codes), EPPO Global Database (shared pests by host), Romanian extension guides (successor values, return intervals).

**Demo scope:** 8–10 crops common in southern Romania plus 1–2 cover crops.
