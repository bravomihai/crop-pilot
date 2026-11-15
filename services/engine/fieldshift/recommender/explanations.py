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
    provisional_rules: bool = False  # P3 rules are a provisional thermal-band shift


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def _lower(name: str) -> str:
    return CRITERION_LABELS[name].lower()


def _interval100(score: Score) -> str:
    return _pts(score.lower) if score.complete else f"{_pts(score.lower)}–{_pts(score.upper)}"


def _interval(score: Score) -> str:
    return _fmt(score.lower) if score.complete else f"{_fmt(score.lower)}–{_fmt(score.upper)}"


def crop_label(names: dict[str, str], crop_id: str) -> str:
    """Display name from the rules, or the ID made readable ('winter_wheat' → 'Winter wheat')
    when the rules do not name the crop (for example outside the covered zones)."""
    return names.get(crop_id) or crop_id.replace("_", " ").capitalize()


def join_sentences(items) -> str:
    """Join complete sentences into one list without doubled punctuation ('..', '.;')."""
    return "; ".join(str(s).strip().rstrip(".") for s in items if str(s).strip()) + "."


def _pts(x: float) -> str:
    """A 0–1 score as points out of 100, matching the score bars in the interface."""
    return f"{x * 100:.0f}"


def _pair100(a: float, b: float) -> tuple[str, str]:
    """Two scores out of 100, with enough decimals that a strict difference stays visible."""
    for digits in (0, 1, 2):
        x, y = f"{a * 100:.{digits}f}", f"{b * 100:.{digits}f}"
        if x != y or a == b:
            return x, y
    return x, y


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
        low.append("some of your priorities could not be scored")
    if ctx.provisional_rules:
        low.append("provisional regional rules: calendars shifted by a thermal band, not validated locally")
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
        medium.append("the what-if change could not be applied")
    if robustness is not None and robustness.reference_status != "feasible":
        medium.append("the plan only works in one of the two climates compared")
    if any(w.severity == "high" for w in evaluation.warnings):
        medium.append("a serious weather or water warning")
    if evaluation.data_gaps:
        medium.append("some data is missing")
    medium.extend(extra_medium)
    if low:
        return LOW, low + medium
    if medium:
        return MEDIUM, medium
    return HIGH, []


def local_checks(evaluation: Evaluation, ctx: PlanContext, extra: tuple[str, ...] = ()) -> list[str]:
    checks = ["Confirm the sowing and harvest windows for this location."]
    if ctx.provisional_rules:
        checks.append(
            "Ask a local agronomist to confirm the crop calendar: the regional rules for this location are provisional."
        )
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
        checks.append("Treat the " + " and ".join(weak) + " scores as estimates.")
    checks.extend(extra)
    checks.extend(evaluation.local_checks)
    return list(dict.fromkeys(checks))


def plan_scores(evaluation: Evaluation) -> dict:
    """Contract `scores`: P3 values for every criterion, null when unknown."""
    return {name: evaluation.criterion(name).score for name in CRITERIA}


def _score_text(score: Score) -> str:
    if score.complete:
        return f"an overall score of {_pts(score.lower)}/100"
    return (
        f"an overall score between {_pts(score.lower)} and {_pts(score.upper)} out of 100 "
        f"(only {score.coverage * 100:.0f}% of your priorities could be scored)"
    )


def _label(number: int, selection: Selection, ctx: PlanContext) -> str:
    if selection.tier == BEST:
        return f"Plan {number} · Best overall match"
    if selection.tier == DIVERSE:
        if selection.strength:
            return f"Plan {number} · Different crops, strongest on {_lower(selection.strength)}"
        return f"Plan {number} · Different crops"
    if selection.tier == SCORE_GAP:
        return f"Plan {number} · Different crops, lower score"
    nearest = ctx.plan_numbers.get(selection.nearest)
    return f"Plan {number} · Similar to plan {nearest}"


def _criterion_lines(evaluation: Evaluation, ctx: PlanContext) -> tuple[list[str], list[str]]:
    benefits: list[str] = []
    tradeoffs: list[str] = []
    for name in CRITERIA:
        if ctx.weights.get(name, 0) <= 0:
            continue
        c = evaluation.criterion(name)
        label = CRITERION_LABELS[name]
        if not c.known:
            tradeoffs.append(f"{label}: not known for this field, so it was left out rather than guessed.")
            continue
        m = ctx.pool_medians.get(name)
        detail = f" {c.summary}" if c.summary else ""
        if ctx.pool_size > 1 and m is not None:
            s_txt, m_txt = _pair100(c.score, m)
            if c.score < m:
                tradeoffs.append(f"{label}: {s_txt}/100, below the typical option ({m_txt}/100).{detail}")
            else:
                benefits.append(f"{label}: {s_txt}/100, as good as or better than the typical option ({m_txt}/100).{detail}")
        else:
            benefits.append(f"{label}: {_pts(c.score)}/100.{detail}")
    return benefits, tradeoffs


def _robustness_lines(robustness: CandidateRobustness | None, with_rank: bool) -> tuple[list[str], list[str]]:
    benefits: list[str] = []
    tradeoffs: list[str] = []
    if robustness is None:
        return benefits, tradeoffs
    if robustness.reference_status == "feasible":
        benefits.append("Also works in the current climate (without the what-if change).")
        if with_rank and robustness.reference_rank is not None and robustness.reference_rank != robustness.scenario_rank:
            tradeoffs.append(
                f"Its ranking depends on the what-if change: number {robustness.scenario_rank} with the change, "
                f"number {robustness.reference_rank} of {robustness.reference_eligible_count} in the current climate."
            )
    else:
        tradeoffs.append(
            "In the current climate (without the what-if change) this sequence does not fit the rules or cannot be "
            f"compared ({robustness.reference_status}); the result depends on the climate assumption."
        )
    parts = ", ".join(f"{_lower(n)} {d * 100:+.0f}" for n, d in robustness.deltas.items() if abs(d) > 1e-9)
    if parts:
        tradeoffs.append(f"Change in scores (out of 100) with the what-if, compared with the current climate: {parts}.")
    return benefits, tradeoffs


def _current_rotation_comparison(score: Score, ctx: PlanContext) -> tuple[str | None, str | None]:
    current = ctx.current_score
    if current is None or current.coverage <= 0 or score.coverage <= 0:
        return None, None
    if score.complete and current.complete:
        text = "{} vs {} out of 100".format(*_pair100(score.lower, current.lower))
    else:
        text = f"{_interval100(score)} vs {_interval100(current)} out of 100"
    if score.lower > current.upper + 1e-9:
        return f"Better overall than your current rotation ({text}).", None
    if score.upper < current.lower - 1e-9:
        return None, f"Worse overall than your current rotation ({text})."
    return None, f"About the same as your current rotation on your priorities ({text})."


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
        benefits.append("No other option beats it on all of your priorities at once.")
    elif pareto.status == DOMINATED and not selection.dominated_by_selected:
        tradeoffs.append(
            f"{len(pareto.dominated_by)} other option(s) are at least as good on every priority; "
            "this one is shown to offer different crops."
        )
    for seq in selection.dominated_by_selected:
        tradeoffs.append(
            f"Plan {ctx.plan_numbers[seq]} is at least as good on every priority."
        )
    if selection.tier == SCORE_GAP:
        tradeoffs.append(
            f"Scores {_pts(selection.score_gap)} points lower overall than plan 1; "
            "shown because no closer option uses different crops."
        )
    if selection.tier == LOW_DIVERSITY:
        tradeoffs.append(
            f"Similar to plan {ctx.plan_numbers[selection.nearest]}; "
            "no more different options fit the rules."
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
        tradeoffs.append(f"Watch out: {w.message}")
    if not benefits:
        benefits.append("Fits the crop rotation rules, with no clear advantage over the other options.")
    if not tradeoffs:
        tradeoffs.append("No trade-offs were identified in the evaluated criteria; local verification is still required.")
    return {"label": _label(number, selection, ctx), "benefits": benefits, "tradeoffs": tradeoffs}


def _common_tail(evaluation: Evaluation, confidence: str, confidence_reasons: list[str], checks: list[str], ctx: PlanContext) -> list[str]:
    parts: list[str] = []
    if ctx.scenario_text and ctx.scenario_status == COMPUTED:
        parts.append(f"The ranking uses {ctx.scenario_text}, compared with the current climate.")
    elif ctx.scenario_text and ctx.scenario_status == UNSUPPORTED:
        parts.append(f"{ctx.scenario_text[0].upper()}{ctx.scenario_text[1:]} could not be applied; the ranking does not reflect it.")
    # The gaps and checks themselves are structured fields (result `data_gaps`, plan
    # `local_checks`) that the interface lists separately; the explanation only points to
    # them instead of repeating the full lists.
    gaps = len(evaluation.data_gaps)
    if gaps:
        parts.append(
            f"{gaps} piece{'s' if gaps != 1 else ''} of information {'are' if gaps != 1 else 'is'} missing or estimated for this plan; "
            "see Missing data under How this was calculated."
        )
    if checks:
        parts.append(
            f"Before acting, review the {len(checks)} local check{'s' if len(checks) != 1 else ''} listed for this plan."
        )
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
        BEST: "Chosen because it scores best overall on your priorities.",
        DIVERSE: "A different crop sequence that scores close to plan 1.",
        SCORE_GAP: "A different crop sequence; it scores noticeably lower than plan 1.",
        LOW_DIVERSITY: "Shown because no other clearly different crop sequences fit the rules.",
    }[selection.tier]
    parts = [
        why,
        f"It has {_score_text(score)}, weighting your priorities as {weights_text(ctx.weights)}.",
    ]
    if pareto.status == "undetermined":
        parts.append("Some priorities could not be scored, so it cannot be compared on all of them.")
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
    tradeoffs = [f"Breaks a crop rotation rule: {v}" for v in violations] + tradeoffs
    if excluded_crops:
        names = ", ".join(crop_label(ctx.crop_names, c) for c in excluded_crops)
        tradeoffs.append(f"Includes crop(s) you excluded from the recommendations: {names}.")
    b, t = _robustness_lines(robustness, with_rank=False)
    benefits += b
    tradeoffs += t
    for w in evaluation.warnings:
        tradeoffs.append(f"Watch out: {w.message}")
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
        f"Your current rotation ({' → '.join(crop_label(ctx.crop_names, c) for c in continuation.cycle)}) "
        "continued for the next three main crops: "
        f"{', '.join(names)}."
    ]
    if not continuation.aligned:
        parts.append("Your crop history does not show where you are in this cycle, so it was continued from its first listed crop.")
    elif continuation.ambiguous:
        parts.append("Several positions in the cycle match your crop history equally well; the earliest one was used.")
    else:
        parts.append(f"The position in the cycle was taken from your most recent crop history ({continuation.matched} matching entr{'y' if continuation.matched == 1 else 'ies'}).")
    parts.append(
        "It was scored the same way as the plans and is shown only for comparison; it is not a recommendation."
    )
    if evaluation.feasibility == INFEASIBLE:
        parts.append(
            f"It breaks {len(violations)} crop rotation rule(s); it is shown as it is, not as a recommendation."
        )
    if score.coverage > 0:
        parts.append(f"It has {_score_text(score)}, weighting your priorities as {weights_text(ctx.weights)}.")
    else:
        parts.append("None of your priorities could be scored for it, so it cannot be compared with the plans.")
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
