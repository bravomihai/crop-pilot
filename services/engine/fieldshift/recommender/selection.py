"""Deterministic selection of up to three useful, distinct alternatives.

Algorithm (greedy, max-marginal-relevance with disclosure tiers):

1. Plan 1 is the top-ranked eligible candidate (see ranking.rank_key).
2. For each next slot, every remaining candidate c gets
     d(c)   = min sequence_distance(c, s) over already selected s
     gap(c) = lower(plan 1) - lower(c)
   and is placed in the first tier it satisfies:
     "diverse"       d >= min_distance and gap <= max_score_gap
     "score_gap"     d >= min_distance                (lower score; disclosed)
     "low_diversity" any remaining distinct sequence  (similar; disclosed)
   Within the best non-empty tier, candidates are ordered by
     (dominated by an already selected plan,
      -[(1-λ)·lower + λ·d + bonus·complementary],
      not Pareto-nondominated, rank position).
   `complementary` is 1 when c's strongest known weighted criterion is not already the
   strongest criterion of a selected plan (diversity of strengths).

Distance: d(a, b) = ½·(positions that differ / 3) + ½·(1 − Jaccard(crop sets)).
It is a structural measure of crop sequences only; it says nothing about agronomic
similarity (e.g. two cereals count as different crops). P3 could later provide crop
families to refine it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import CRITERIA, PLAN_COUNT, RecommenderConfig
from .pareto import NONDOMINATED, ParetoInfo, dominates
from .ranking import Score

BEST, DIVERSE, SCORE_GAP, LOW_DIVERSITY = "best", "diverse", "score_gap", "low_diversity"


@dataclass(frozen=True)
class Selection:
    sequence: tuple[str, ...]
    rank: int  # 1-based position in the full ranking of eligible candidates
    tier: str
    min_distance: float | None = None
    nearest: tuple[str, ...] | None = None
    score_gap: float = 0.0
    dominated_by_selected: tuple[tuple[str, ...], ...] = ()
    strength: str | None = None


def sequence_distance(a, b) -> float:
    a, b = tuple(a), tuple(b)
    if len(a) != len(b):
        raise ValueError("sequences must have equal length")
    if not a:
        return 0.0
    positional = sum(x != y for x, y in zip(a, b)) / len(a)
    sa, sb = set(a), set(b)
    jaccard = len(sa & sb) / len(sa | sb)
    return 0.5 * positional + 0.5 * (1 - jaccard)


def strongest_criterion(profile: dict, weights: dict) -> str | None:
    best, best_score = None, None
    for name in CRITERIA:  # fixed order makes ties deterministic
        score = profile.get(name)
        if weights.get(name, 0) > 0 and score is not None and (best_score is None or score > best_score):
            best, best_score = name, score
    return best


def select_diverse(
    ranked: list[tuple[str, ...]],
    scores: dict[tuple[str, ...], Score],
    profiles: dict[tuple[str, ...], dict],
    pareto: dict[tuple[str, ...], ParetoInfo],
    weights: dict[str, float],
    config: RecommenderConfig,
    count: int = PLAN_COUNT,
) -> list[Selection]:
    if not ranked:
        return []
    positions = {seq: i + 1 for i, seq in enumerate(ranked)}
    objectives = tuple(n for n in CRITERIA if weights.get(n, 0) > 0)
    top = ranked[0]
    best_lower = scores[top].lower
    selected = [Selection(top, 1, BEST, strength=strongest_criterion(profiles[top], weights))]
    remaining = [seq for seq in ranked[1:] if seq != top]
    lam = config.diversity_weight
    while remaining and len(selected) < count:
        strengths = {s.strength for s in selected if s.strength}
        options = []
        for seq in remaining:
            distances = [(sequence_distance(seq, s.sequence), s.sequence) for s in selected]
            d, nearest = min(distances, key=lambda x: (x[0], positions[x[1]]))
            gap = max(0.0, best_lower - scores[seq].lower)
            if d >= config.min_distance and gap <= config.max_score_gap + config.epsilon:
                tier = 0
            elif d >= config.min_distance:
                tier = 1
            else:
                tier = 2
            strength = strongest_criterion(profiles[seq], weights)
            complementary = strength is not None and strength not in strengths
            utility = (1 - lam) * scores[seq].lower + lam * d + (
                config.complementarity_bonus if complementary else 0.0
            )
            dominated_by = tuple(
                s.sequence
                for s in selected
                if dominates(profiles[s.sequence], profiles[seq], objectives, config.epsilon)
            )
            key = (
                tier,
                bool(dominated_by),
                -round(utility, 12),
                pareto[seq].status != NONDOMINATED,
                positions[seq],
            )
            options.append((key, seq, d, nearest, gap, dominated_by, strength))
        key, seq, d, nearest, gap, dominated_by, strength = min(options, key=lambda o: o[0])
        selected.append(
            Selection(
                sequence=seq,
                rank=positions[seq],
                tier=(DIVERSE, SCORE_GAP, LOW_DIVERSITY)[key[0]],
                min_distance=d,
                nearest=nearest,
                score_gap=gap,
                dominated_by_selected=dominated_by,
                strength=strength,
            )
        )
        remaining.remove(seq)
    return selected
