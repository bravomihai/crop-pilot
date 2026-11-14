"""Deterministic, evidence-grounded plan text and qualitative confidence.

Every sentence is built from P3 evaluation fields or P4 comparison results. Nothing here
invents yields, profits, measurements or probabilities. User-facing text is English.

Terminology: "reference climate" = the request without the hypothetical scenario.
"Current rotation" / `baseline` = the farmer's own rotation continued. They are separate.

Confidence (qualitative evidence grade, NOT a calibrated probability):
  low    if the evaluation is a fixture; or weighted coverage < 1; or a weighted
         criterion rests on "assumed" evidence or cites no source
  medium if not low but any of: a requested criterion (weighted or not) unknown; a
         criterion rests on "estimated" evidence; crop history missing; the most recent
         history entry comes from a satellite classification; soil not lab-measured;
         requested scenario not applied by P3; feasibility differs between the scenario
         and the reference climate; a high-severity warning; P3 reported data gaps; or
         (current rotation only) its position in the cycle had to be assumed
  high   otherwise
History sources "typed", "apia" and "spray_records" are treated as documented evidence.
"unknown" or a missing source does not lower confidence (that would assume the record is
wrong), but adds a local check asking the farmer to confirm the previous crop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import median

from .config import CRITERIA, CRITERION_LABELS, REQUIRED_CRITERIA
from .evaluation import INFEASIBLE, Evaluation
from .pareto import DOMINATED, NONDOMINATED, ParetoInfo
from .ranking import Score
from .scenarios import COMPUTED, UNSUPPORTED, CandidateRobustness
from .selection import BEST, DIVERSE, LOW_DIVERSITY, SCORE_GAP, Selection

LOW, MEDIUM, HIGH = "low", "medium", "high"
CONFIDENCE_TEXT = {LOW: "Low", MEDIUM: "Medium", HIGH: "High"}
DOCUMENTED_HISTORY = ("typed", "apia", "spray_records")


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
    requested_criteria: tuple = REQUIRED_CRITERIA  # criteria present in request priorities
    previous_crop_source: str | None = None  # source of the most recent history entry
    current_score: Score | None = None  # score of the farmer's current rotation, if shown


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def _lower(name: str) -> str:
    return CRITERION_LABELS[name].lower()


def _interval(score: Score) -> str:
    return _fmt(score.lower) if score.complete else f"{_fmt(score.lower)}–{_fmt(score.upper)}"


def _pair(a: float, b: float) -> tuple[str, str]:
    """Format two values with enough decimals that a strict difference stays visible."""
    for digits in (2, 3, 4):
        x, y = f"{a:.{digits}f}", f"{b:.{digits}f}"
        if x != y or a == b:
            return x, y
    return x, y


def weights_text(weights: dict[str, float]) -> str:
    shown = [n for n in CRITERIA if n in REQUIRED_CRITERIA or weights.get(n, 0) > 0]
    return ", ".join(f"{_lower(n)} {weights[n] * 100:.0f}%" for n in shown)


def assess_confidence(
    evaluation: Evaluation,
    score: Score,
    ctx: PlanContext,
    robustness: CandidateRobustness | None,
    extra_medium: tuple[str, ...] = (),
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
            if ctx.weights.get(name, 0) <= 0 and name in ctx.requested_criteria:
                medium.append(f"{_lower(name)}: not evaluated")
        elif c.basis == "estimated":
            medium.append(f"{_lower(name)}: estimate, not an observation")
    if ctx.history_missing:
        medium.append("no crop history provided")
    elif ctx.previous_crop_source == "satellite":
        medium.append("previous crop taken from a satellite classification")
    if ctx.soil_weak:
        medium.append("soil not measured by a laboratory")
    if ctx.scenario_status == UNSUPPORTED:
        medium.append("the scenario was not applied by the evaluator")
    if robustness is not None and robustness.reference_status != "feasible":
        medium.append("feasibility differs between the scenario and the reference climate")
    if any(w.severity == "high" for w in evaluation.warnings):
        medium.append("high-severity warning from the evaluator")
    if evaluation.data_gaps:
        medium.append("data gaps reported by the evaluator")
    medium.extend(extra_medium)
    if low:
        return LOW, low + medium
    if medium:
        return MEDIUM, medium
    return HIGH, []


def local_checks(evaluation: Evaluation, ctx: PlanContext, extra: tuple[str, ...] = ()) -> list[str]:
    checks = ["Confirm the sowing and harvest windows for this location."]
    if ctx.history_missing:
        checks.append("Confirm compatibility with the previous crop (no crop history was provided).")
    elif ctx.previous_crop_source == "satellite":
        checks.append("Confirm the previous crop: it comes from a satellite classification.")
    elif ctx.previous_crop_source not in DOCUMENTED_HISTORY:
        checks.append("Confirm the previous crop: the source of the crop history was not stated.")
    if ctx.soil_weak:
        checks.append("Check the soil data (no laboratory analysis was provided).")
    if ctx.irrigated:
        checks.append("Confirm that irrigation water is available when the crops need it.")
    weak = [_lower(n) for n in CRITERIA if evaluation.criterion(n).known and evaluation.criterion(n).basis in ("estimated", "assumed")]
    if weak:
        checks.append("Review the estimated criteria (" + ", ".join(weak) + ").")
    checks.extend(extra)
    checks.extend(f"P3: {c}" for c in evaluation.local_checks)
    return list(dict.fromkeys(checks))


def plan_scores(evaluation: Evaluation) -> dict:
    """Contract `scores`: P3 values for every criterion, null when unknown."""
    return {name: evaluation.criterion(name).score for name in CRITERIA}


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


def _criterion_lines(evaluation: Evaluation, ctx: PlanContext) -> tuple[list[str], list[str]]:
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
        if ctx.pool_size > 1 and m is not None:
            s_txt, m_txt = _pair(c.score, m)
            if c.score < m:
                tradeoffs.append(f"{label}: P3 score {s_txt}, below the median of feasible candidates ({m_txt}).{detail}")
            else:
                benefits.append(f"{label}: P3 score {s_txt}, at or above the median of feasible candidates ({m_txt}).{detail}")
        else:
            benefits.append(f"{label}: P3 score {_fmt(c.score)} out of 1.{detail}")
    return benefits, tradeoffs


def _robustness_lines(robustness: CandidateRobustness | None, with_rank: bool) -> tuple[list[str], list[str]]:
    benefits: list[str] = []
    tradeoffs: list[str] = []
    if robustness is None:
        return benefits, tradeoffs
    if robustness.reference_status == "feasible":
        benefits.append("Remains feasible under the reference climate (without the scenario).")
        if with_rank and robustness.reference_rank is not None and robustness.reference_rank != robustness.scenario_rank:
            tradeoffs.append(
                f"Its ranking depends on the scenario: rank {robustness.scenario_rank} under the scenario, "
                f"rank {robustness.reference_rank} of {robustness.reference_eligible_count} under the reference climate."
            )
    else:
        tradeoffs.append(
            "Under the reference climate (without the scenario) this sequence is not feasible or cannot be compared "
            f"(status: {robustness.reference_status}); the result depends on the climate assumption."
        )
    parts = ", ".join(f"{_lower(n)} {d:+.2f}" for n, d in robustness.deltas.items() if abs(d) > 1e-9)
    if parts:
        tradeoffs.append(f"Change in P3 scores under the scenario relative to the reference climate: {parts}.")
    return benefits, tradeoffs


def _current_rotation_comparison(score: Score, ctx: PlanContext) -> tuple[str | None, str | None]:
    current = ctx.current_score
    if current is None or current.coverage <= 0 or score.coverage <= 0:
        return None, None
    text = f"{_interval(score)} vs {_interval(current)}"
    if score.lower > current.upper + 1e-9:
        return f"Higher weighted score than your current rotation ({text}).", None
    if score.upper < current.lower - 1e-9:
        return None, f"Lower weighted score than your current rotation ({text})."
    return None, f"Not clearly different from your current rotation on the weighted priorities ({text})."


def build_texts(
    number: int,
    selection: Selection,
    evaluation: Evaluation,
    score: Score,
    pareto: ParetoInfo,
    robustness: CandidateRobustness | None,
    ctx: PlanContext,
) -> dict:
    benefits, tradeoffs = _criterion_lines(evaluation, ctx)
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
    b, t = _robustness_lines(robustness, with_rank=True)
    benefits += b
    tradeoffs += t
    better, worse = _current_rotation_comparison(score, ctx)
    if better:
        benefits.append(better)
    if worse:
        tradeoffs.append(worse)
    for w in evaluation.warnings:
        tradeoffs.append(f"Evaluator warning: {w.message}")
    if not benefits:
        benefits.append("Feasible according to the P3 evaluator, with no distinct advantage over the other candidates.")
    if not tradeoffs:
        tradeoffs.append("No trade-offs were identified in the evaluated criteria; local verification is still required.")
    return {"label": _label(number, selection, ctx), "benefits": benefits, "tradeoffs": tradeoffs}


def _common_tail(evaluation: Evaluation, confidence: str, confidence_reasons: list[str], checks: list[str], ctx: PlanContext) -> list[str]:
    parts = [
        "Feasibility, the crop calendar and the criterion scores come from the P3 evaluator; P4 only "
        "compares and selects. Scores are not yields, profits or probabilities."
    ]
    if ctx.scenario_text and ctx.scenario_status == COMPUTED:
        parts.append(f"The ranking uses {ctx.scenario_text}, compared against the reference climate.")
    elif ctx.scenario_text and ctx.scenario_status == UNSUPPORTED:
        parts.append(f"{ctx.scenario_text[0].upper()}{ctx.scenario_text[1:]} was not applied by the evaluator; the ranking does not reflect it.")
    if evaluation.data_gaps:
        parts.append("Data gaps reported by the evaluator: " + "; ".join(evaluation.data_gaps) + ".")
    parts.append("Local checks before acting: " + " ".join(checks))
    reason_text = f" ({'; '.join(confidence_reasons)})" if confidence_reasons else ""
    parts.append(
        f"{CONFIDENCE_TEXT[confidence]} confidence{reason_text}: a qualitative grade of the evidence, not a probability of success."
    )
    return parts


def build_explanation(
    selection: Selection,
    evaluation: Evaluation,
    score: Score,
    pareto: ParetoInfo,
    confidence: str,
    confidence_reasons: list[str],
    ctx: PlanContext,
    checks: list[str] | None = None,
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
    checks = checks if checks is not None else local_checks(evaluation, ctx)
    parts += _common_tail(evaluation, confidence, confidence_reasons, checks, ctx)
    return " ".join(parts)


def build_current_rotation_texts(
    continuation,
    evaluation: Evaluation,
    score: Score,
    robustness: CandidateRobustness | None,
    excluded_crops: list[str],
    ctx: PlanContext,
) -> dict:
    """Fields for the contract `baseline` plan (the farmer's current rotation continued)."""
    benefits, tradeoffs = _criterion_lines(evaluation, ctx)
    violations = list(evaluation.violations)
    tradeoffs = [f"Breaks an agronomic rule (P3): {v}" for v in violations] + tradeoffs
    if excluded_crops:
        tradeoffs.append(f"Includes crop(s) you excluded from the recommendations: {', '.join(excluded_crops)}.")
    b, t = _robustness_lines(robustness, with_rank=False)
    benefits += b
    tradeoffs += t
    for w in evaluation.warnings:
        tradeoffs.append(f"Evaluator warning: {w.message}")
    if not benefits:
        benefits.append("Continues the rotation you already follow; no other advantage was identified in the evaluated criteria.")
    if not tradeoffs:
        tradeoffs.append("No trade-offs were identified in the evaluated criteria; local verification is still required.")

    extra_medium, extra_checks = [], []
    if not continuation.aligned:
        extra_medium.append("position in the current rotation assumed")
        extra_checks.append("Confirm which crop of your current rotation comes next (it could not be read from the crop history).")
    elif continuation.ambiguous:
        extra_medium.append("position in the current rotation ambiguous")
        extra_checks.append("Confirm which crop of your current rotation comes next (the crop history matches more than one position).")
    confidence, reasons = assess_confidence(evaluation, score, ctx, robustness, tuple(extra_medium))
    checks = local_checks(evaluation, ctx, tuple(extra_checks))

    names = [ctx.crop_names.get(c, c) for c in continuation.sequence]
    parts = [
        f"Your current rotation ({' → '.join(continuation.cycle)}) continued for the next three main crops: "
        f"{', '.join(names)}."
    ]
    if not continuation.aligned:
        parts.append("Your crop history does not show where you are in this cycle, so it was continued from its first listed crop.")
    elif continuation.ambiguous:
        parts.append("Several positions in the cycle match your crop history equally well; the earliest one was used.")
    else:
        parts.append(f"The position in the cycle was taken from your most recent crop history ({continuation.matched} matching entr{'y' if continuation.matched == 1 else 'ies'}).")
    parts.append(
        "It was evaluated by P3 in the same way as the recommended options and is shown for comparison only; "
        "it is not a recommendation and does not count toward the result status."
    )
    if evaluation.feasibility == INFEASIBLE:
        parts.append(
            f"P3 reports that this sequence breaks {len(violations)} agronomic rule(s); it is shown as it is, not as a recommendation."
        )
    if score.coverage > 0:
        parts.append(f"It has {_score_text(score)}, using your normalized priorities ({weights_text(ctx.weights)}).")
    else:
        parts.append("P3 provided no scores for your weighted priorities, so it cannot be compared with the options on them.")
    parts += _common_tail(evaluation, confidence, reasons, checks, ctx)
    return {
        "label": "Current rotation continued",
        "benefits": benefits,
        "tradeoffs": tradeoffs,
        "explanation": " ".join(parts),
        "confidence": confidence,
        "local_checks": checks,
        "violations": violations,
    }


def pool_medians(profiles: list[dict]) -> dict[str, float]:
    result = {}
    for name in CRITERIA:
        values = [p[name] for p in profiles if p.get(name) is not None]
        if values:
            result[name] = median(values)
    return result
