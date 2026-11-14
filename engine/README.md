# Engine (Python)

One Python service with three packages that run in the same process. The Next.js backend calls it over HTTP ([contracts/api.md](../contracts/api.md)).

| Package | Owner | Input → output |
|---|---|---|
| [`fieldshift/data`](fieldshift/data/__init__.py) | P2: data integration | coordinates + years → `FieldData` |
| [`fieldshift/evaluator`](fieldshift/evaluator/__init__.py) | P3: agronomic evaluator | rotation + `FieldData` + `CropRules` → `Evaluation` |
| [`fieldshift/recommender`](fieldshift/recommender/__init__.py) | P4: recommendation engine | `FarmRequest` + evaluator → `AnalysisResult` |
| [`rules/`](rules/README.md) | P3 | crop tables, rules, successor matrix (`CropRules` JSON) |

The data service fetches daily weather from NASA POWER and topsoil pH / organic carbon from SoilGrids, then normalizes them into `FieldData`. NASA POWER's daily weather is also used to calculate FAO-56 reference evapotranspiration. SoilGrids is optional: if its service or a point's values are unavailable, the response records the missing data in `quality` rather than inventing values.

SRTM slope, SMAP root-zone soil moisture and NEX-GDDP-CMIP6 scenario deltas are not integrated yet; they are explicitly listed as missing. The evaluator and recommender still return their contract examples.

## Run

```bash
cd engine
python -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
pytest
uvicorn fieldshift.api:app --reload --port 8000
```

Then open http://localhost:8000/docs.

## Rules

- Your output must pass `validate("<format>", output)`. The tests check this.
- Don't import another package's internals; call only `fetch_field_data`, `evaluate`, `load_rules`, `recommend`.
- No priorities inside the evaluator; no data fetching inside the recommender.
- Every number shown to the farmer needs a source id.
