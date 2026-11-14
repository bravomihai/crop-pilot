"""P4 owns generation, constraints, comparison and explanations.

Generate THREE distinct plans of THREE successive main crops. Apply priorities only here.
Call the P3 evaluator; preserve source references and caveats. Calendar time matters.
Return fewer than three plans with status limited/insufficient_data when necessary.
Never fill missing alternatives with infeasible or duplicate plans.

Public entry points:
- `recommend_rotations(request, environment, rules, evaluate) -> list[plan]` (team
  interface). The returned list is a `PlanList`: a normal list of plans that also carries
  `.outcome` (sources, assumptions, data gaps and the optional current-rotation
  `baseline`), which `pipeline.py` uses to build the full result.
- `recommend(...) -> RecommendationOutcome` (the same outcome, directly).

The P3 evaluation shape P4 reads is a proposal documented in `evaluation.py` and in
docs/P4_IMPLEMENTATION_REPORT.md. Until P3 implements `evaluate`, calls propagate
NotImplementedError and computed mode stays unavailable (HTTP 503).
"""

from typing import Callable

from .config import RecommenderConfig
from .engine import PlanList, RecommendationOutcome, recommend

__all__ = ["PlanList", "RecommendationOutcome", "RecommenderConfig", "recommend", "recommend_rotations"]


def recommend_rotations(
    request: dict, environment: dict, rules: dict, evaluate: Callable
) -> list[dict]:
    return PlanList(recommend(request, environment, rules, evaluate))
