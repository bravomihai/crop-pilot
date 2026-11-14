"""P4 owns generation, constraints, comparison and explanations.

Generate three distinct plans of three successive main crops. Apply priorities only here,
call the P3 evaluator, preserve source references and caveats, and return fewer than three
plans when there are not enough supported alternatives.
"""

from .config import RecommenderConfig
from .engine import PlanList, RecommendationOutcome, recommend


def recommend_rotations(request, environment, rules, evaluate):
    return PlanList(recommend(request, environment, rules, evaluate))


__all__ = [
    "PlanList",
    "RecommendationOutcome",
    "RecommenderConfig",
    "recommend",
    "recommend_rotations",
]
