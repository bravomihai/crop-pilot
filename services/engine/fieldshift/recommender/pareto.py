"""Pareto dominance over the farmer's positively weighted objectives.

Profiles map objective → score in [0, 1] or None (unknown). Rules:

- Dominance is decided only when BOTH profiles know every objective. Otherwise the pair
  is incomparable (`dominates` returns None); missing values are never favourable.
- A candidate with any unknown objective gets status "undetermined": P4 does not claim
  it is or is not on the frontier.
- "nondominated" means: no fully evaluated candidate dominates it. It is a statement
  about the evaluated, fully known set only, not global Pareto optimality.
"""

from __future__ import annotations

from dataclasses import dataclass

NONDOMINATED, DOMINATED, UNDETERMINED = "nondominated", "dominated", "undetermined"


@dataclass(frozen=True)
class ParetoInfo:
    status: str
    dominated_by: tuple = ()


def dominates(a: dict, b: dict, objectives, epsilon: float = 1e-9) -> bool | None:
    """True if a dominates b, False if not, None if they are not comparable."""
    if not objectives:
        return None
    if any(a.get(o) is None or b.get(o) is None for o in objectives):
        return None
    no_worse = all(a[o] >= b[o] - epsilon for o in objectives)
    better = any(a[o] > b[o] + epsilon for o in objectives)
    return no_worse and better


def pareto_analysis(profiles: dict, objectives, epsilon: float = 1e-9) -> dict:
    """Same semantics as pairwise `dominates`, with a safe pruning step.

    If a dominates b then sum(a) > sum(b) - k·epsilon, so for each b only candidates whose
    coordinate sum is at least that large need to be compared. Results are identical to
    the naive O(n²) check; only the work is reduced.
    """
    objectives = tuple(objectives)
    result = {key: ParetoInfo(UNDETERMINED) for key in profiles}
    if not objectives:
        return result
    vectors = {
        key: tuple(p[o] for o in objectives)
        for key, p in profiles.items()
        if all(p.get(o) is not None for o in objectives)
    }
    order = sorted(vectors, key=lambda k: (-sum(vectors[k]), k))
    sums = [sum(vectors[k]) for k in order]
    slack = len(objectives) * epsilon
    for index, key in enumerate(order):
        b = vectors[key]
        threshold = sums[index] - slack
        by = []
        for j, other in enumerate(order):
            if sums[j] < threshold:
                break  # sorted by descending sum: no later candidate can dominate
            if other == key:
                continue
            a = vectors[other]
            if all(x >= y - epsilon for x, y in zip(a, b)) and any(x > y + epsilon for x, y in zip(a, b)):
                by.append(other)
        result[key] = ParetoInfo(DOMINATED if by else NONDOMINATED, tuple(sorted(by)))
    return result
