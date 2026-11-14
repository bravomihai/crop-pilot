"""Hypothetical climate scenario handling and robustness comparison.

The scenario (`temp_change_c`, `rain_change_pct`) is a what-if input, not a NASA
forecast. P3 alone converts it into agronomic evaluations. P4:

- evaluates every candidate with the request as given (primary ranking);
- if the scenario is non-zero, evaluates the SAME candidates with a baseline copy of the
  request (both deltas 0) and compares feasibility, rank and criterion scores;
- declares robustness "unsupported" when any primary evaluation does not confirm
  `scenario_applied: true`, in which case no baseline comparison is made and the
  ranking is labelled as not reflecting the scenario.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .config import CRITERIA

NOT_REQUESTED, UNSUPPORTED, COMPUTED = "not_requested", "unsupported", "computed"


def scenario_of(request: dict) -> tuple[float, float]:
    scenario = request.get("scenario") or {}
    return float(scenario.get("temp_change_c", 0) or 0), float(scenario.get("rain_change_pct", 0) or 0)


def is_baseline(request: dict) -> bool:
    return scenario_of(request) == (0.0, 0.0)


def baseline_request(request: dict) -> dict:
    baseline = copy.deepcopy(request)
    baseline["scenario"] = {"temp_change_c": 0, "rain_change_pct": 0}
    return baseline


@dataclass(frozen=True)
class CandidateRobustness:
    baseline_status: str  # feasibility class under baseline (see engine classes)
    baseline_rank: int | None  # 1-based among baseline-eligible candidates
    scenario_rank: int | None
    baseline_eligible_count: int
    deltas: dict = field(default_factory=dict)  # criterion → scenario − baseline (both known)


@dataclass(frozen=True)
class Robustness:
    status: str
    per_candidate: dict = field(default_factory=dict)


def criterion_deltas(primary, baseline) -> dict[str, float]:
    deltas = {}
    for name in CRITERIA:
        a, b = primary.criterion(name), baseline.criterion(name)
        if a.known and b.known:
            deltas[name] = a.score - b.score
    return deltas
