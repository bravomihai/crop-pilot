"""FarmRequest → AnalysisResult. The only function the API calls."""

import uuid
from datetime import datetime, timezone

from .contracts import AnalysisResult, FarmRequest
from .data import fetch_field_data
from .evaluator import evaluate, load_rules
from .recommender import recommend

HISTORY_YEARS = 10


def centroid(boundary: dict) -> tuple[float, float]:
    """(lat, lon) mean of the outer ring vertices. Good enough for 0.5° POWER cells."""
    ring = boundary["coordinates"][0][:-1] or boundary["coordinates"][0]
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lat, lon


def analyze(farm: FarmRequest) -> AnalysisResult:
    lat, lon = centroid(farm["field"]["boundary"])
    end_year = datetime.now(timezone.utc).year - 1
    field_data = fetch_field_data(lat, lon, end_year - HISTORY_YEARS + 1, end_year)
    rules = load_rules()
    result = recommend(farm, field_data, rules, evaluate)
    result["analysis_id"] = f"an_{uuid.uuid4().hex[:12]}"
    return result
