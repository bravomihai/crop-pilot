"""P4: recommender. Generates rotations, calls the evaluator, ranks by farmer priorities, explains.

Steps:
  1. Candidate rotations of farm["rotation_years"] crops from CropRules (optionally with
     cover crops in bare windows), excluding farm["constraints"]["excluded_crops"].
  2. evaluate() each; drop infeasible ones (except the existing rotation).
  3. total = sum(normalised weight x score) over known criteria.
  4. Pick the top alternatives, preferring ones that differ from each other.
  5. Fill why / evidence / benefits / risks / local_checks from the Evaluation using
     templates (no facts that are not in the Evaluation). An LLM may rephrase later.
  6. Confidence from history source, successor-matrix coverage, NDVI coverage and how much
     scores change across scenarios.
"""

from datetime import datetime, timezone
from typing import Callable

from ..contracts import AnalysisResult, CropRules, Evaluation, FarmRequest, FieldData, example

Evaluate = Callable[..., Evaluation]


def normalise_weights(priorities: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in priorities.values() if v > 0)
    if total == 0:
        raise ValueError("At least one priority must be > 0")
    return {k: round(v / total, 3) for k, v in priorities.items() if v > 0}


def recommend(
    farm: FarmRequest,
    field_data: FieldData,
    rules: CropRules,
    evaluate: Evaluate,
    n_alternatives: int = 2,
) -> AnalysisResult:
    """Return an AnalysisResult: existing rotation first, then n_alternatives ranked alternatives.

    TODO(P4): real generation, ranking and explanations.
    """
    result = example("analysis-result")
    result["farm_id"] = farm.get("farm_id", result["farm_id"])
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    result["scenario"] = farm["scenario"]
    result["weights_used"] = normalise_weights(farm["priorities"])
    result["strategies"][0]["sequence"] = list(farm["current_rotation"])
    return result
