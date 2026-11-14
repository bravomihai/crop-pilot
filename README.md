# Field Shift: rotation planning with NASA data

NASA Space Apps Challenge 2026, challenge **"Field Shift: Adapting Farms with NASA Data"**.

A decision-support tool that compares a farmer's **current crop rotation with at least two alternatives** for a specific field. Each option shows why it was suggested, the evidence behind it (NASA Earth observations replayed over the field's own recent seasons and future climate scenarios), its benefits, its risks and what to check with a local agronomist. It supports farmer judgment; it doesn't replace it.

Farmers use it in the browser or by **SMS / WhatsApp**.

## How it works

```
Form / SMS → fetch field data → generate rotations → evaluate → rank by priorities → results
```

1. The farmer draws the field and enters crop history, the current rotation, priorities (water, soil, income, …) and constraints.
2. The engine pulls NASA data for the field (POWER climate, SMAP soil moisture, SRTM slope, CMIP6 scenarios, …).
3. It generates candidate rotations, filters out agronomically bad ones with sourced rules, and scores each on nine criteria.
4. Farmer priorities weight the scores; the existing rotation plus the best alternatives are returned with explanations and a confidence level.
5. What-ifs (priorities, climate scenario, rain/temperature sliders) re-run the ranking.

Details: [docs/architecture.md](docs/architecture.md).

## Repository

```
contracts/   Shared data formats (JSON Schema + examples) and API docs. Start here.
frontend/    React + Vite web app                                     P1
engine/      Python: data service (P2), evaluator (P3), recommender (P4)
backend/     Next.js API, storage, SMS/WhatsApp webhook               P5
infra/       AWS deployment notes                                     P5
docs/        Architecture and decisions
notebooks/   Data exploration
```

| Person | Builds | Done when |
|---|---|---|
| P1: Frontend | Map and field drawing, form, charts, rotation comparison, scenario controls | The whole flow works in the browser |
| P2: Data integration | NASA data fetch, cleaning, general indicators, cache | The app gets the data for any field on its own |
| P3: Agronomic evaluator | Crop tables and rules with sources, compatibility checks, water/temperature/soil calculations | Any rotation of supported crops is evaluated automatically |
| P4: Recommendation engine | Rotation generation, choosing alternatives, ranking by priorities, scenario re-runs, explanations | The app produces the options and the reasons for them |
| P5: Backend and infra | API, database, saving farms and analyses, SMS, deployment | The app runs online and all parts talk to each other |

**Every component starts out working on the example data in [`contracts/examples/`](contracts/examples/)**, so each person can build and test their part alone and the full flow works from the start.

## Run locally

Each folder's README has the details.

```bash
# Engine (Python 3.11+)
cd engine && pip install -e ".[dev]" && pytest && uvicorn fieldshift.api:app --port 8000

# Backend (Node 20+), in another terminal
cd backend && npm install && npm run dev

# Frontend, in another terminal
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Or run backend + engine together with `docker compose up --build`.

Check that the examples still match the contracts: `python contracts/validate.py`.

## Working together

See [CONTRIBUTING.md](CONTRIBUTING.md): work on your own branch, open a PR into `main`, one teammate reviews.

## Data sources

[NASA POWER](https://power.larc.nasa.gov/) · [SMAP](https://smap.jpl.nasa.gov/) · [ECOSTRESS](https://ecostress.jpl.nasa.gov/) · [GPM IMERG](https://gpm.nasa.gov/) · Landsat / MODIS · GRACE-FO · SRTM · [NEX-GDDP-CMIP6](https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6) · Sentinel-2 · FAO EcoCrop · FAO GAEZ v4 · FAO-56 · ISRIC SoilGrids · EuroCrops
