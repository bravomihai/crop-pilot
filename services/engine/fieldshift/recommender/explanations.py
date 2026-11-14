"""Deterministic, evidence-grounded plan text and qualitative confidence.

Every sentence is built from P3 evaluation fields or P4 comparison results. Nothing here
invents yields, profits, measurements or probabilities. User-facing text is English.

Confidence (qualitative evidence grade, NOT a calibrated probability):
  low    if the evaluation is a fixture; or weighted coverage < 1; or a weighted
         criterion rests on "assumed" evidence or cites no source
  medium if not low but any of: some criterion (weighted or not) unknown; a criterion
         rests on "estimated" evidence; crop history missing; soil not provided or
         unknown/farmer estimate; requested scenario not applied by P3; feasibility
         differs between scenario and baseline; a high-severity warning; or P3 reported
         data gaps for this plan
  high   otherwise
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import median

from .config import CRITERIA, CRITERION_LABELS
from .evaluation import Evaluation
from .pareto import DOMINATED, NONDOMINATED, ParetoInfo
from .ranking import Score
from .scenarios import COMPUTED, UNSUPPORTED, CandidateRobustness
from .selection import BEST, DIVERSE, LOW_DIVERSITY, SCORE_GAP, Selection

LOW, MEDIUM, HIGH = "low", "medium", "high"
CONFIDENCE_TEXT = {LOW: "Low", MEDIUM: "Medium", HIGH: "High"}


@dataclass
class PlanContext:
    weights: dict[str, float]
    available_from: date
    crop_names: dict[str, str]
    pool_medians: dict[str, float]  # criterion → median score among eligible candidates
    pool_size: int
    history_missing: bool
    soil_weak: bool
    irrigated: bool
    scenario_status: str
    scenario_text: str | None
    plan_numbers: dict = field(default_factory=dict)  # sequence → 1-based plan number


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def _lower(name: str) -> str:
    return CRITERION_LABELS[name].lower()


def weights_text(weights: dict[str, float]) -> str:
    return ", ".join(f"{_lower(n)} {weights[n] * 100:.0f}%" for n in CRITERIA)


def assess_confidence(
    evaluation: Evaluation,
    score: Score,
    ctx: PlanContext,
    robustness: CandidateRobustness | None,
) -> tuple[str, list[str]]:
    low, medium = [], []
    if evaluation.fixture:
        low.append("test (fixture) evaluation, not an agronomic result")
    if score.coverage < 1:
        low.append("not every weighted priority has a P3 score")
    for name in score.known:
        c = evaluation.criterion(name)
        if c.basis == "assumed":
            low.append(f"{_lower(name)}: evidence is assumed")
        if not c.source_ids:
            low.append(f"{_lower(name)}: no source cited")
    for name in CRITERIA:
        c = evaluation.criterion(name)
        if not c.known:
            if ctx.weights.get(name, 0) <= 0:
                medium.append(f"{_lower(name)}: not evaluated")
        elif c.basis == "estimated":
            medium.append(f"{_lower(name)}: estimate, not an observation")
    if ctx.history_missing:
        medium.append("no crop history provided")
    if ctx.soil_weak:
        medium.append("soil not measured by a laboratory")
    if ctx.scenario_status == UNSUPPORTED:
        medium.append("the scenario was not applied by the evaluator")
    if robustness is not None and robustness.baseline_status != "feasible":
        medium.append("feasibility differs between the scenario and the baseline")
    if any(w.severity == "high" for w in evaluation.warnings):
        medium.append("high-severity warning from the evaluator")
    if evaluation.data_gaps:
        medium.append("data gaps reported by the evaluator")
    if low:
        return LOW, low + medium
    if medium:
        return MEDIUM, medium
    return HIGH, []


def _score_text(score: Score) -> str:
    if score.complete:
        return f"a weighted score of {_fmt(score.lower)} out of 1"
    return (
        f"a weighted score between {_fmt(score.lower)} and {_fmt(score.upper)} out of 1 "
        f"(an interval: {score.coverage * 100:.0f}% of the priority weight is backed by evidence)"
    )


def _label(number: int, selection: Selection, ctx: PlanContext) -> str:
    if selection.tier == BEST:
        return f"Option {number} — highest weighted score"
    if selection.tier == DIVERSE:
        if selection.strength:
            return f"Option {number} — distinct alternative (strength: {_lower(selection.strength)})"
        return f"Option {number} — distinct alternative"
    if selection.tier == SCORE_GAP:
        return f"Option {number} — distinct alternative with a lower score"
    nearest = ctx.plan_numbers.get(selection.nearest)
    return f"Option {number} — similar to Option {nearest}"


def build_texts(
    number: int,
    selection: Selection,
    evaluation: Evaluation,
    score: Score,
    pareto: ParetoInfo,
    robustness: CandidateRobustness | None,
    ctx: PlanContext,
) -> dict:
    benefits: list[str] = []
    tradeoffs: list[str] = []
    for name in CRITERIA:
        if ctx.weights.get(name, 0) <= 0:
            continue
        c = evaluation.criterion(name)
        label = CRITERION_LABELS[name]
        if not c.known:
            tradeoffs.append(f"{label}: not evaluated by P3 — not treated as an average or zero value.")
            continue
        m = ctx.pool_medians.get(name)
        detail = f" P3 evidence: {c.summary}" if c.summary else ""
        if ctx.pool_size > 1 and m is not None and c.score < m:
            tradeoffs.append(f"{label}: P3 score {_fmt(c.score)}, below the median of feasible candidates ({_fmt(m)}).{detail}")
        elif ctx.pool_size > 1 and m is not None:
            benefits.append(f"{label}: P3 score {_fmt(c.score)}, at or above the median of feasible candidates ({_fmt(m)}).{detail}")
        else:
            benefits.append(f"{label}: P3 score {_fmt(c.score)} out of 1.{detail}")
    if pareto.status == NONDOMINATED:
        benefits.append(
            "Pareto non-dominated among fully evaluated candidates: no other plan is at least as "
            "good on all of your priorities and better on at least one."
        )
    elif pareto.status == DOMINATED and not selection.dominated_by_selected:
        tradeoffs.append(
            f"Pareto-dominated by {len(pareto.dominated_by)} feasible candidate(s) that were not selected; "
            "kept for crop-sequence diversity."
        )
    for seq in selection.dominated_by_selected:
        tradeoffs.append(
            f"Pareto-dominated by Option {ctx.plan_numbers[seq]}: it is not better on any evaluated criterion."
        )
    if selection.tier == SCORE_GAP:
        tradeoffs.append(
            f"Its guaranteed weighted score is {_fmt(selection.score_gap)} lower than Option 1; "
            "included because no distinct alternative with a comparable score exists."
        )
    if selection.tier == LOW_DIVERSITY:
        tradeoffs.append(
            f"Similar to Option {ctx.plan_numbers[selection.nearest]} (distance {_fmt(selection.min_distance)}); "
            "no more distinct feasible alternatives were available."
        )
    if robustness is not None:
        if robustness.baseline_status == "feasible" and robustness.baseline_rank is not None:
            benefits.append("Remains feasible under baseline conditions (without the scenario).")
            if robustness.baseline_rank != robustness.scenario_rank:
                tradeoffs.append(
                    f"Its ranking depends on the scenario: rank {robustness.scenario_rank} under the scenario, "
                    f"rank {robustness.baseline_rank} of {robustness.baseline_eligible_count} without it."
                )
        else:
            tradeoffs.append(
                "Under baseline conditions (without the scenario) the plan is not feasible or cannot be compared "
                f"(status: {robustness.baseline_status}); it depends on the climate assumption."
            )
        if robustness.deltas:
            parts = ", ".join(
                f"{_lower(n)} {d:+.2f}" for n, d in robustness.deltas.items() if abs(d) > 1e-9
            )
            if parts:
                tradeoffs.append(f"Change in P3 scores under the scenario relative to the baseline: {parts}.")
    for w in evaluation.warnings:
        tradeoffs.append(f"Evaluator warning: {w.message}")
    if not benefits:
        benefits.append("Feasible according to the P3 evaluator, with no distinct advantage over the other candidates.")
    if not tradeoffs:
        tradeoffs.append("No trade-offs were identified in the evaluated criteria; local verification is still required.")
    return {"label": _label(number, selection, ctx), "benefits": benefits, "tradeoffs": tradeoffs}


def build_explanation(
    selection: Selection,
    evaluation: Evaluation,
    score: Score,
    pareto: ParetoInfo,
    confidence: str,
    confidence_reasons: list[str],
    ctx: PlanContext,
) -> str:
    why = {
        BEST: "Selected as the plan with the highest guaranteed weighted score among the feasible sequences.",
        DIVERSE: "Selected as an alternative with a different crop sequence and a score close to Option 1.",
        SCORE_GAP: "Selected as a distinct alternative; its score is noticeably lower than Option 1.",
        LOW_DIVERSITY: "Selected because no other sufficiently different feasible sequences were available.",
    }[selection.tier]
    parts = [
        why,
        f"It has {_score_text(score)}, using your normalized priorities ({weights_text(ctx.weights)}).",
    ]
    if pareto.status == NONDOMINATED:
        parts.append("It lies on the Pareto frontier of the fully evaluated candidates.")
    elif pareto.status == "undetermined":
        parts.append("Its Pareto position cannot be determined because some criteria are missing.")
    parts.append(
        "Feasibility, the crop calendar and the criterion scores come from the P3 evaluator; P4 only "
        "compares and selects. Scores are not yields, profits or probabilities."
    )
    if ctx.scenario_text and ctx.scenario_status == COMPUTED:
        parts.append(f"The ranking uses {ctx.scenario_text}, compared against baseline conditions.")
    elif ctx.scenario_text and ctx.scenario_status == UNSUPPORTED:
        parts.append(f"{ctx.scenario_text[0].upper()}{ctx.scenario_text[1:]} was not applied by the evaluator; the ranking does not reflect it.")
    if evaluation.data_gaps:
        parts.append("Data gaps reported by the evaluator: " + "; ".join(evaluation.data_gaps) + ".")
    checks = ["sowing and harvest windows for this location"]
    if ctx.history_missing:
        checks.append("compatibility with the previous crop (no crop history provided)")
    if ctx.soil_weak:
        checks.append("soil data")
    if ctx.irrigated:
        checks.append("availability of irrigation water")
    weak = [_lower(n) for n in CRITERIA if evaluation.criterion(n).known and evaluation.criterion(n).basis in ("estimated", "assumed")]
    if weak:
        checks.append("estimated criteria (" + ", ".join(weak) + ")")
    parts.append("To verify with a local agronomist: " + "; ".join(checks) + ".")
    reason_text = f" ({'; '.join(confidence_reasons)})" if confidence_reasons else ""
    parts.append(
        f"{CONFIDENCE_TEXT[confidence]} confidence{reason_text}: a qualitative grade of the evidence, not a probability of success."
    )
    return " ".join(parts)


def pool_medians(profiles: list[dict]) -> dict[str, float]:
    result = {}
    for name in CRITERIA:
        values = [p[name] for p in profiles if p.get(name) is not None]
        if values:
            result[name] = median(values)
    return result
