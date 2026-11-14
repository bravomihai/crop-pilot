"""Internal HTTP API, called only by the Next.js backend. See contracts/api.md.

Run locally:  uvicorn fieldshift.api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .contracts import validate
from .data import fetch_field_data
from .evaluator import evaluate as evaluate_rotation
from .evaluator import load_rules
from .pipeline import analyze as run_analysis

app = FastAPI(title="Field Shift engine")


def _check(name: str, data: dict) -> None:
    errors = validate(name, data)
    if errors:
        raise HTTPException(status_code=422, detail={"code": "validation_error", "errors": errors})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/analyze")
def analyze(farm: dict) -> dict:
    _check("farm-request", farm)
    result = run_analysis(farm)
    _check("analysis-result", result)
    return result


class FieldDataQuery(BaseModel):
    lat: float
    lon: float
    start_year: int
    end_year: int


@app.post("/field-data")
def field_data(q: FieldDataQuery) -> dict:
    return fetch_field_data(q.lat, q.lon, q.start_year, q.end_year)


class EvaluateQuery(BaseModel):
    farm: dict
    rotation: list[str]
    cover_crops: list[dict] | None = None


@app.post("/evaluate")
def evaluate(q: EvaluateQuery) -> dict:
    _check("farm-request", q.farm)
    from .pipeline import centroid

    lat, lon = centroid(q.farm["field"]["boundary"])
    fd = fetch_field_data(lat, lon, 2015, 2024)
    return evaluate_rotation(q.rotation, q.farm, fd, load_rules(), q.cover_crops)
