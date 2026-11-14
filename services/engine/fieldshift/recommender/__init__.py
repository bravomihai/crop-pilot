"""P4 owns generation, constraints, comparison and explanations.

Generate THREE distinct plans of THREE successive main crops. Apply priorities only here.
Call the P3 evaluator; preserve source references and caveats. Calendar time matters.
Return fewer than three plans with status limited/insufficient_data when necessary.
Never fill missing alternatives with infeasible or duplicate plans.

Public entry points:
- `recommend_rotations(request, environment, rules, evaluate) -> list[plan]` (team interface)
- `recommend(...) -> RecommendationOutcome` (plans plus the sources, assumptions and data
  gaps the pipeline needs to build a contract-valid result)

The P3 evaluation shape P4 reads is a proposal documented in `evaluation.py` and in
docs/P4_IMPLEMENTATION_REPORT.md. Until P3 implements `evaluate`, calls propagate
NotImplementedError and computed mode stays unavailable (HTTP 503).
"""

from typing import Callable

from .config import RecommenderConfig
from .engine import RecommendationOutcome, recommend

__all__ = ["RecommendationOutcome", "RecommenderConfig", "recommend", "recommend_rotations"]


def recommend_rotations(
    request: dict, environment: dict, rules: dict, evaluate: Callable
) -> list[dict]:
    return recommend(request, environment, rules, evaluate).plans
