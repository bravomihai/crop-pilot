# Contracts

The shared data formats between components. **Agree here first, then build against the examples.** Every component can be developed and tested alone using the files in `examples/`.

| Format | Produced by | Consumed by | Schema | Example |
|---|---|---|---|---|
| `FarmRequest` | Frontend form (P1) / SMS flow | Backend (P5) → engine (P2, P4) | [farm-request](schemas/farm-request.schema.json) | [example](examples/farm-request.example.json) |
| `FieldData` | Data service (P2) | Evaluator (P3) | [field-data](schemas/field-data.schema.json) | [example](examples/field-data.example.json) |
| `CropRules` | Evaluator data (P3) | Evaluator (P3) | [crop-rules](schemas/crop-rules.schema.json) | [example](examples/crop-rules.example.json) |
| `Evaluation` | Evaluator (P3) | Recommender (P4) | [evaluation](schemas/evaluation.schema.json) | [example](examples/evaluation.example.json) |
| `AnalysisResult` | Recommender (P4) | Backend (P5) → frontend (P1), SMS | [analysis-result](schemas/analysis-result.schema.json) | [example](examples/analysis-result.example.json) |

Shared definitions (crop ids, criteria, scenario, confidence) live in [common.schema.json](schemas/common.schema.json).

HTTP endpoints and the SMS flow are described in [api.md](api.md).

> **All values in `examples/` are invented** for development. The agronomic values in `crop-rules.example.json` point to a `placeholder_agronomy` source and must be replaced with cited sources before the demo.

## Pipeline

```
FarmRequest ──► P2 fetch_field_data ──► FieldData ─┐
     │                                             ├──► P3 evaluate(rotation) ──► Evaluation ──► P4 rank + explain ──► AnalysisResult
     └──────────► P4 generate rotations ───────────┘           ▲
                                                    CropRules ─┘
```

## Rules of thumb

- **Crop ids** are lowercase snake_case (`maize`, `winter_wheat`) and must exist in `CropRules`. Display names come from `CropRules.crops[].name`.
- **Criteria** are the same nine names everywhere: farmer priorities, evaluation scores and result scores.
- **Scores are 0–1, higher is better.** `null` with `unknown: true` means "no data". Never put a neutral 0.5 in its place: unknowns lower confidence.
- **Priorities are applied only by the recommender (P4).** The evaluator scores rotations without knowing what the farmer wants.
- **Every claim carries a source id.** The explanation text may only restate what is in `detail`, `evidence` and the scores.
- **Strategy 0 is always the farmer's existing rotation**, even if it breaks rules (the violations are listed).

## Changing a contract

1. Edit the schema and the matching example in the same commit.
2. Run `python contracts/validate.py` (needs `pip install jsonschema`).
3. Tell the people whose components produce or consume that format.

You can also validate your own output: `python contracts/validate.py path/to/my-analysis-result.json` (the file name must contain the format name).
