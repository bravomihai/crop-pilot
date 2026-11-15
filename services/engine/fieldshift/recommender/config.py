"""Tunable search/selection limits for P4. None of these are agronomic parameters.

Every value is a decision-support heuristic about *how* P4 searches and compares the
evaluations returned by P3. They never change feasibility, calendars or criterion scores.
"""

from dataclasses import dataclass

CRITERIA: tuple[str, ...] = ("water", "soil", "climate", "productivity")
# Required in every request; `productivity` is optional (absent = not weighted).
REQUIRED_CRITERIA: tuple[str, ...] = ("water", "soil", "climate")
CRITERION_LABELS = {"water": "Water", "soil": "Soil", "climate": "Climate", "productivity": "Productivity"}
SEQUENCE_LENGTH = 3  # contract: crop_count is the literal 3
PLAN_COUNT = 3  # contract: at most three plans


@dataclass(frozen=True)
class RecommenderConfig:
    # Upper bound on evaluated sequences per climate condition. When the full space
    # (n_crops ** 3) is larger, a deterministic SHA-256 sample is evaluated and the
    # truncation is reported in data_gaps.
    max_candidates: int = 500
    # Minimum share of the farmer's (normalized) priority weight that must be backed by
    # known P3 scores for a plan to be returned at all.
    min_coverage: float = 0.5
    # Diversity may only promote a candidate whose guaranteed weighted score is within
    # this absolute gap of plan 1; larger gaps are allowed only as a disclosed fallback.
    max_score_gap: float = 0.15
    # Minimum sequence distance (see selection.sequence_distance) for "meaningfully
    # different" alternatives.
    min_distance: float = 0.4
    # Weight of diversity versus score in the greedy max-marginal-relevance step.
    diversity_weight: float = 0.3
    # Small bonus when an alternative's strongest criterion is not yet represented.
    complementarity_bonus: float = 0.05
    # Numeric tolerance for Pareto comparisons and ties.
    epsilon: float = 1e-9

    def __post_init__(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        for name in ("min_coverage", "max_score_gap", "min_distance", "diversity_weight"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be within [0, 1]")
        if self.complementarity_bonus < 0 or self.epsilon <= 0:
            raise ValueError("complementarity_bonus must be >= 0 and epsilon > 0")
