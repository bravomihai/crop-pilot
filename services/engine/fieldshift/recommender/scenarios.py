"""Hypothetical climate scenario handling and robustness comparison.

Terminology: the climate comparison uses a REFERENCE climate (both scenario deltas 0).
This is unrelated to the contract's `baseline` plan, which is the farmer's current
rotation continued (see engine.build_current_baseline).

The scenario (`temp_change_c`, `rain_change_pct`) is a what-if input, not a NASA
forecast. P3 alone converts it into agronomic evaluations. P4:

- evaluates every candidate with the request as given (primary ranking);
- if the scenario is non-zero, evaluates the SAME candidates with a reference copy of the
  request (both deltas 0) and compares feasibility, rank and criterion scores;
- declares robustness "unsupported" when any primary evaluation does not confirm
  `scenario_applied: true`, in which case no reference comparison is made and the
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


def is_reference_climate(request: dict) -> bool:
    return scenario_of(request) == (0.0, 0.0)


def reference_request(request: dict) -> dict:
    reference = copy.deepcopy(request)
    reference["scenario"] = {"temp_change_c": 0, "rain_change_pct": 0}
    return reference


@dataclass(frozen=True)
class CandidateRobustness:
    reference_status: str  # feasibility class under the reference climate (engine classes)
    reference_rank: int | None  # 1-based among reference-eligible candidates
    scenario_rank: int | None
    reference_eligible_count: int
    deltas: dict = field(default_factory=dict)  # criterion → scenario − reference (both known)


def criterion_deltas(primary, reference) -> dict[str, float]:
    deltas = {}
    for name in CRITERIA:
        a, b = primary.criterion(name), reference.criterion(name)
        if a.known and b.known:
            deltas[name] = a.score - b.score
    return deltas
