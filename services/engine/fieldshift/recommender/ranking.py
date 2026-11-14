"""Transparent weighted ranking with explicit missing-data intervals.

Weights: the farmer's priorities (0–5 each) normalized to sum to 1. All-zero priorities
are invalid input per docs/api.md ("at least one positive priority") and raise.

Scores: P3 criterion scores in [0, 1] (higher = better). An unknown score is NOT
replaced by 0, 0.5 or any other value. Instead each plan gets an interval:

    lower    = Σ_known w_i · s_i                  (as if every unknown were the worst, 0)
    upper    = lower + Σ_unknown w_i               (as if every unknown were the best, 1)
    coverage = Σ_known w_i                         (share of priority weight with evidence)

Plans are ranked by the guaranteed (lower) score, then coverage, then upper, then the
crop sequence string. A plan with less evidence therefore cannot outrank a fully
evaluated plan by luck of missing data; when coverage is 1 the interval collapses to a
single value. Zero-weight criteria do not affect the score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import CRITERIA
from .evaluation import Evaluation

ALL_ZERO_MESSAGE = "At least one priority must be positive"


def normalize_priorities(priorities: dict) -> dict[str, float]:
    if not isinstance(priorities, dict):
        raise ValueError("priorities must be an object")
    values = {}
    for name in CRITERIA:
        value = priorities.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"priority {name} must be a number")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"priority {name} must be a finite non-negative number")
        values[name] = float(value)
    total = sum(values.values())
    if total <= 0:
        raise ValueError(ALL_ZERO_MESSAGE)
    return {name: values[name] / total for name in CRITERIA}


@dataclass(frozen=True)
class Score:
    lower: float
    upper: float
    coverage: float
    known: tuple[str, ...]  # positively weighted criteria with a P3 score
    missing: tuple[str, ...]  # positively weighted criteria without a P3 score

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def value(self) -> float | None:
        """Single weighted value, only defined when every weighted criterion is known."""
        return self.lower if self.complete else None


def score_evaluation(evaluation: Evaluation, weights: dict[str, float]) -> Score:
    lower = coverage = 0.0
    known, missing = [], []
    for name in CRITERIA:
        weight = weights.get(name, 0.0)
        if weight <= 0:
            continue
        criterion = evaluation.criterion(name)
        if criterion.known:
            lower += weight * criterion.score
            coverage += weight
            known.append(name)
        else:
            missing.append(name)
    # Guard against floating drift so a complete plan has coverage exactly 1.
    coverage = 1.0 if not missing else min(coverage, 1.0)
    upper = lower + (1.0 - coverage)
    return Score(lower, min(upper, 1.0), coverage, tuple(known), tuple(missing))


def rank_key(sequence: tuple[str, ...], score: Score) -> tuple:
    return (-round(score.lower, 12), -round(score.coverage, 12), -round(score.upper, 12), sequence)


def rank(scores: dict[tuple[str, ...], Score]) -> list[tuple[str, ...]]:
    """Deterministic ranking of sequences by `rank_key`."""
    return sorted(scores, key=lambda seq: rank_key(seq, scores[seq]))
