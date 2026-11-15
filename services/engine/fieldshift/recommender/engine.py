"""P4 orchestration: generate → evaluate (P3) → classify → rank → Pareto → select → explain.

Optionally also evaluates the farmer's `current_rotation` continued for three crops and
returns it as the contract's `baseline` plan. The baseline never enters selection and
never counts toward `status`.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .config import CRITERIA, PLAN_COUNT, REQUIRED_CRITERIA, SEQUENCE_LENGTH, RecommenderConfig
from .evaluation import FEASIBLE, INFEASIBLE, UNKNOWN, Evaluation, parse_evaluation, valid_source
from .explanations import (
    PlanContext,
    assess_confidence,
    build_current_rotation_texts,
    build_explanation,
    build_texts,
    crop_label,
    join_sentences,
    local_checks,
    plan_scores,
    pool_medians,
    weights_text,
)
from .generation import crop_catalog, generate_candidates
from .pareto import ParetoInfo, pareto_analysis
from .ranking import Score, normalize_priorities, rank, score_evaluation
from .rotation import continue_rotation
from .scenarios import (
    COMPUTED,
    NOT_REQUESTED,
    UNSUPPORTED,
    CandidateRobustness,
    criterion_deltas,
    is_reference_climate,
    reference_request,
    scenario_of,
)
from .selection import PREFERRED, Selection, select_diverse
from .validation import history_issues, ordered_history, validate_calendar

CALENDAR_INVALID = "calendar_invalid"


@dataclass
class Candidate:
    sequence: tuple[str, ...]
    evaluation: Evaluation
    status: str  # feasible | infeasible | unknown | calendar_invalid
    reasons: tuple[str, ...] = ()
    score: Score | None = None
    eligible: bool = False
    ineligible_reason: str | None = None
    source_ids: tuple[str, ...] = ()
    unresolved_ids: tuple[str, ...] = ()

    @property
    def profile(self) -> dict:
        return {n: self.evaluation.criterion(n).score for n in CRITERIA}


@dataclass
class RecommendationOutcome:
    plans: list[dict]
    sources: list[dict]
    assumptions: list[str]
    data_gaps: list[str]
    diagnostics: dict = field(default_factory=dict)
    fixture: bool = False
    baseline: dict | None = None  # contract `baseline`: the current rotation continued

    @property
    def status(self) -> str:
        return "complete" if len(self.plans) == PLAN_COUNT else "limited" if self.plans else "insufficient_data"


class PlanList(list):
    """The `list[plan]` returned by `recommend_rotations`, carrying the full outcome.

    It behaves exactly like a list of plans (the team interface), while the pipeline can
    read `.outcome` for sources, assumptions, data gaps and the baseline. Callers or test
    stubs that return a plain list keep working; the pipeline then falls back to the
    environment/rules metadata only.
    """

    def __init__(self, outcome: RecommendationOutcome):
        super().__init__(outcome.plans)
        self.outcome = outcome


def _classify(evaluation: Evaluation, available_from: date) -> tuple[str, tuple[str, ...]]:
    if evaluation.feasibility == INFEASIBLE:
        return INFEASIBLE, evaluation.violations or ("reported infeasible by evaluator",)
    if evaluation.feasibility != FEASIBLE:
        return UNKNOWN, evaluation.contract_errors or ("evaluator could not establish feasibility",)
    if evaluation.calendar is None:
        return UNKNOWN, (evaluation.calendar_error or "calendar missing",)
    errors = validate_calendar(evaluation.calendar, evaluation.rotation, available_from)
    if errors:
        return CALENDAR_INVALID, tuple(errors)
    return FEASIBLE, ()


def _evaluate_all(sequences, request, environment, rules, evaluate: Callable, available_from):
    """Call P3 once per sequence. NotImplementedError and other errors propagate."""
    result = {}
    for seq in sequences:
        raw = evaluate(list(seq), copy.deepcopy(request), environment, rules)
        evaluation = parse_evaluation(raw, seq)
        status, reasons = _classify(evaluation, available_from)
        result[seq] = Candidate(seq, evaluation, status, reasons)
    return result


def _cited_ids(evaluation: Evaluation, score: Score) -> list[str]:
    ids = list(evaluation.source_ids)
    for name in score.known:
        ids.extend(evaluation.criterion(name).source_ids)
    for step in evaluation.calendar or ():
        ids.extend(step.source_ids)
    return ids


def _resolve_sources(cand: Candidate, weights, known_ids: set) -> None:
    cand.score = score_evaluation(cand.evaluation, weights)
    cited = _cited_ids(cand.evaluation, cand.score)
    cand.source_ids = tuple(sorted({i for i in cited if i in known_ids}))
    cand.unresolved_ids = tuple(sorted({i for i in cited if i not in known_ids}))


def _score_and_filter(candidates: dict, weights, known_ids: set, config: RecommenderConfig) -> None:
    for cand in candidates.values():
        if cand.status != FEASIBLE:
            continue
        _resolve_sources(cand, weights, known_ids)
        if cand.score.coverage <= 0 or cand.score.coverage + config.epsilon < config.min_coverage:
            cand.ineligible_reason = "coverage"
        elif not cand.source_ids:
            cand.ineligible_reason = "no_sources"
        else:
            cand.eligible = True


def _counts(candidates: dict) -> dict:
    counts = {FEASIBLE: 0, INFEASIBLE: 0, UNKNOWN: 0, CALENDAR_INVALID: 0}
    for cand in candidates.values():
        counts[cand.status] += 1
    counts["eligible"] = sum(c.eligible for c in candidates.values())
    counts["low_coverage"] = sum(c.ineligible_reason == "coverage" for c in candidates.values())
    counts["no_sources"] = sum(c.ineligible_reason == "no_sources" for c in candidates.values())
    return counts


def _merge_sources(*groups) -> list[dict]:
    merged, seen = [], set()
    for group in groups:
        for source in group:
            if isinstance(source, dict) and source.get("id") not in seen:
                seen.add(source.get("id"))
                merged.append(source)
    return merged


# Above this, the lowland/plateau crop rules may not describe what is grown (disclosure only).
HIGH_ELEVATION_M = 800


def _ignored_input_notes(constraints: dict, catalog: dict, excluded: set) -> list[str]:
    """Say when a request input has no effect, instead of ignoring it silently."""
    notes = []
    label = lambda c: crop_label({k: v.name for k, v in catalog.items() if v.name}, c)
    if constraints.get("max_irrigation_mm") is not None and not constraints.get("irrigated"):
        notes.append("An irrigation limit was given, but irrigation is off; the plans are rain-fed.")
    selected = list(dict.fromkeys(constraints.get("selected_crops") or []))
    if selected and not constraints.get("selected_crops_only", False):
        notes.append("A crop shortlist was given but not applied (shortlist-only is off); all regional crops were considered.")
    elif selected:
        unknown = [c for c in selected if c not in catalog]
        if unknown:
            notes.append(f"Shortlisted crop(s) without regional rules were skipped: {', '.join(label(c) for c in unknown)}.")
        both = [c for c in selected if c in excluded]
        if both:
            notes.append(f"Crop(s) both shortlisted and excluded were excluded: {', '.join(label(c) for c in both)}.")
    return notes


def _dedupe(items) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


_WINTERKILL = re.compile(r"Winterkill risk for (.+?) ignores snow cover")


def _merge_winterkill(gaps: list[str]) -> list[str]:
    """One winterkill note for all winter crops shown, instead of one per crop."""
    names = [m.group(1) for g in gaps if (m := _WINTERKILL.match(g))]
    if len(names) < 2:
        return gaps
    crops = ", ".join(names[:-1]) + " and " + names[-1]
    merged = (
        f"Winterkill risk for {crops} ignores snow cover, which protects winter crops; "
        "check winter hardiness locally."
    )
    out, placed = [], False
    for g in gaps:
        if _WINTERKILL.match(g):
            if not placed:
                out.append(merged)
                placed = True
        else:
            out.append(g)
    return out


def _steps(evaluation: Evaluation, ctx: PlanContext) -> list[dict]:
    steps = []
    for index, step in enumerate(evaluation.calendar):
        sowing_start = step.sowing_start
        reason = step.reason or "Window taken from the regional crop calendar."
        if index == 0 and sowing_start < ctx.available_from:
            sowing_start = ctx.available_from
            reason += f" The start of sowing was moved to the field availability date ({ctx.available_from.isoformat()})."
        steps.append(
            {
                "order": index + 1,
                "crop_id": step.crop_id,
                "crop_name": step.crop_name or ctx.crop_names.get(step.crop_id) or step.crop_id,
                "sowing_window": {"start": sowing_start.isoformat(), "end": step.sowing_end.isoformat()},
                "harvest_window": {"start": step.harvest_start.isoformat(), "end": step.harvest_end.isoformat()},
                "reason": reason,
            }
        )
    return steps


def recommend(
    request: dict,
    environment: dict,
    rules: dict,
    evaluate: Callable,
    config: RecommenderConfig | None = None,
) -> RecommendationOutcome:
    config = config or RecommenderConfig()
    if request.get("crop_count", SEQUENCE_LENGTH) != SEQUENCE_LENGTH:
        raise ValueError("crop_count must be 3")
    environment = environment or {}
    rules = rules or {}
    weights = normalize_priorities(request["priorities"])
    requested_criteria = tuple(n for n in CRITERIA if n in REQUIRED_CRITERIA or n in request["priorities"])
    available_from = date.fromisoformat(request["available_from"])
    constraints = request.get("constraints") or {}
    excluded = set(constraints.get("excluded_crops") or [])
    history = ordered_history(request.get("history") or [])
    previous_source = (history[-1].get("source") or "unknown") if history else None
    soil = request.get("soil") or {}
    temp, rain = scenario_of(request)
    scenario_requested = not is_reference_climate(request)
    scenario_text = (
        f"the hypothetical scenario of {temp:+.1f} °C and {rain:+.0f}% precipitation" if scenario_requested else None
    )

    base_sources = _merge_sources(environment.get("sources") or [], rules.get("sources") or [])
    assumptions = [
        "Each plan contains three successive main crops; this does not mean three years, and the plan does not repeat automatically.",
        f"Priorities were normalized to: {weights_text(weights)}.",
        "Scores (0–100) compare the options with each other; they are not yields, profits or probabilities.",
        "Unknown values are not replaced with zero or an average value; the score becomes an interval instead.",
    ]
    if weights.get("productivity", 0) > 0:
        assumptions.append("Productivity is a relative production-potential score, not a yield or profit forecast.")
    if scenario_text:
        assumptions.append(f"Requested {scenario_text}; this is a hypothetical assumption, not a NASA forecast.")
    data_gaps: list[str] = []
    if not history:
        data_gaps.append("No crop history was provided; compatibility with the previous crop cannot be verified.")
    elif previous_source == "satellite":
        data_gaps.append(
            "The most recent crop history entry comes from a satellite classification, which is weaker evidence "
            "than typed or documented records; previous-crop checks are less certain."
        )
    elif previous_source == "unknown":
        data_gaps.append("The source of the most recent crop history entry was not stated.")
    if not soil or soil.get("source", "unknown") == "unknown":
        regional_soil = (environment.get("static") or {}).get("soil") or environment.get("soil")
        data_gaps.append(
            "No soil analysis was entered; the soil assessment uses regional soil-map estimates (SoilGrids, 0–30 cm), "
            "not a sample from this field."
            if regional_soil
            else "No soil analysis was entered and no regional soil estimate is available; the soil assessment is uncertain."
        )

    catalog, catalog_issues = crop_catalog(rules)
    candidate_catalog = catalog
    if constraints.get("selected_crops_only", False):
        selected = set(constraints.get("selected_crops") or [])
        candidate_catalog = {
            crop_id: crop
            for crop_id, crop in catalog.items()
            if crop_id in selected
        }
    data_gaps.extend(g for g in (rules.get("data_gaps") or []) if isinstance(g, str))
    data_gaps.extend(catalog_issues)
    assumptions.extend(_ignored_input_notes(constraints, catalog, excluded))
    elevation = ((environment.get("static") or {}).get("elevation_m"))
    if isinstance(elevation, (int, float)) and not isinstance(elevation, bool) and elevation > HIGH_ELEVATION_M:
        data_gaps.append(
            f"The weather data's elevation is about {elevation:.0f} m. The regional crop rules describe lowland "
            "and plateau field crops; check locally that these crops are grown at this altitude."
        )
    data_gaps.extend(history_issues(request, set(catalog)))
    diagnostics: dict = {
        "crops": sorted(candidate_catalog),
        "excluded": sorted(excluded),
    }

    def finish(plans, sources, fixture=False, baseline=None) -> RecommendationOutcome:
        if len(plans) < PLAN_COUNT:
            data_gaps.append(
                f"{len(plans)} feasible, documented plan(s) were found; the result was not padded with invented options."
            )
        return RecommendationOutcome(
            plans, sources, _dedupe(assumptions), _merge_winterkill(_dedupe(data_gaps)), diagnostics, fixture, baseline
        )

    candidate_set = generate_candidates(
        candidate_catalog, excluded, config.max_candidates
    )
    diagnostics.update(total_space=candidate_set.total_space, generated=len(candidate_set.candidates), truncated=candidate_set.truncated)
    if candidate_set.truncated:
        data_gaps.append(
            f"The search space ({candidate_set.total_space} sequences) exceeds the limit of {config.max_candidates}; "
            "a deterministic sample was evaluated, so good plans may remain unexplored."
        )
    if not candidate_set.candidates:
        if constraints.get("selected_crops_only", False):
            data_gaps.append(
                "No candidate crops remain after applying the selected-crop shortlist and exclusions."
            )
        elif catalog:
            data_gaps.append("The regional rules offer no candidate crops after the exclusions were applied.")
        elif not rules.get("data_gaps"):
            # With no rules at all, P3's own reason (forwarded above) already says why.
            data_gaps.append("The regional rules contain no candidate crops.")

    # Primary evaluation: the request as given (including any scenario).
    candidates = _evaluate_all(candidate_set.candidates, request, environment, rules, evaluate, available_from)

    # The farmer's current rotation is evaluated with the same evaluator and request, but
    # without the exclusion list: its `violations` must be agronomic rules only, and the
    # farmer's own exclusions are reported separately ("Includes crop(s) you excluded").
    continuation = None
    current = None
    agronomy_request = {**request, "constraints": {**constraints, "excluded_crops": []}}
    if request.get("current_rotation"):
        continuation = continue_rotation(request["current_rotation"], history)
        seq = continuation.sequence
        current = candidates.get(seq) or _evaluate_all([seq], agronomy_request, environment, rules, evaluate, available_from)[seq]
        diagnostics["current_rotation_sequence"] = list(seq)

    evaluated = list(candidates.values()) + ([current] if current else [])
    evaluation_sources = [s for c in evaluated for s in c.evaluation.sources]
    known_ids = {s["id"] for s in _merge_sources(base_sources, evaluation_sources) if valid_source(s)}
    _score_and_filter(candidates, weights, known_ids, config)
    fixture = any(c.evaluation.fixture for c in evaluated)
    if fixture:
        assumptions.append("Evaluations come from a test (fixture) evaluator; they are not agronomic results.")

    # Climate scenario support and robustness (compared with the reference climate).
    if not scenario_requested:
        scenario_status = NOT_REQUESTED
    elif not [c for c in evaluated if c.evaluation.feasibility != UNKNOWN]:
        scenario_status = "not_evaluated"  # P3 evaluated nothing; no claim either way
    elif all(c.evaluation.scenario_applied for c in evaluated if c.evaluation.feasibility != UNKNOWN):
        scenario_status = COMPUTED
    else:
        scenario_status = UNSUPPORTED
        data_gaps.append(
            "The evaluator did not confirm that the hypothetical scenario was applied; the ranking does not reflect the scenario and robustness was not computed."
        )
    diagnostics["scenario_status"] = scenario_status

    counts = _counts(candidates)
    diagnostics["counts"] = counts
    if candidates:
        assumptions.append(
            f"Search: {len(candidates)} sequences evaluated from {len(candidate_set.crops)} available crops; "
            f"{counts[FEASIBLE]} feasible, {counts[INFEASIBLE]} infeasible, {counts[UNKNOWN]} with unknown feasibility, "
            f"{counts[CALENDAR_INVALID]} with an invalid calendar."
        )
    if counts[UNKNOWN]:
        data_gaps.append(f"{counts[UNKNOWN]} crop sequences could not be fully evaluated and were left out; missing evidence is never treated as a pass.")
    if counts[CALENDAR_INVALID]:
        data_gaps.append(f"{counts[CALENDAR_INVALID]} sequences had overlapping calendars or calendars incompatible with the field availability date and were excluded.")
    if counts["low_coverage"]:
        data_gaps.append(f"{counts['low_coverage']} crop sequences that fit the rules had scores for less than {config.min_coverage * 100:.0f}% of the priority weight and were not proposed.")
    if counts["no_sources"]:
        data_gaps.append(f"{counts['no_sources']} feasible sequences cited no verifiable sources and were not proposed.")

    eligible = {seq: c for seq, c in candidates.items() if c.eligible}
    scores = {seq: c.score for seq, c in eligible.items()}
    ranked = rank(scores)
    profiles = {seq: c.profile for seq, c in eligible.items()}
    objectives = tuple(n for n in CRITERIA if weights[n] > 0)
    pareto = pareto_analysis(profiles, objectives, config.epsilon)
    diagnostics["pareto_frontier"] = sum(p.status == "nondominated" for p in pareto.values())

    robustness: dict[tuple, CandidateRobustness] = {}
    reference: dict = {}
    if scenario_status == COMPUTED:
        ref_req = reference_request(request)
        reference = _evaluate_all(candidate_set.candidates, ref_req, environment, rules, evaluate, available_from)
        if current is not None and current.sequence not in reference:
            reference.update(_evaluate_all([current.sequence], reference_request(agronomy_request), environment, rules, evaluate, available_from))
        ref_known = known_ids | {s["id"] for c in reference.values() for s in c.evaluation.sources}
        _score_and_filter(reference, weights, ref_known, config)
        ref_ranked = rank({seq: c.score for seq, c in reference.items() if c.eligible and seq in candidates})
        ref_pos = {seq: i + 1 for i, seq in enumerate(ref_ranked)}
        scen_pos = {seq: i + 1 for i, seq in enumerate(ranked)}
        for seq in eligible:
            r = reference[seq]
            robustness[seq] = CandidateRobustness(
                reference_status=r.status if r.eligible or r.status != FEASIBLE else "not_comparable",
                reference_rank=ref_pos.get(seq),
                scenario_rank=scen_pos[seq],
                reference_eligible_count=len(ref_ranked),
                deltas=criterion_deltas(candidates[seq].evaluation, r.evaluation),
            )
        diagnostics["reference_counts"] = _counts({s: c for s, c in reference.items() if s in candidates})

    selections = select_diverse(ranked, scores, profiles, pareto, weights, config)
    preferred_crop = request.get("preferred_crop")
    if preferred_crop and not any(preferred_crop in selection.sequence for selection in selections):
        matching = next((sequence for sequence in ranked if preferred_crop in sequence), None)
        if matching is not None:
            preferred = Selection(matching, ranked.index(matching) + 1, PREFERRED)
            if len(selections) == PLAN_COUNT:
                selections[-1] = preferred
            else:
                selections.append(preferred)
        else:
            data_gaps.append(
                f"No eligible rotation containing {preferred_crop.replace('_', ' ')} was found "
                "among the evaluated sequences; other rotations may not have been evaluated."
            )
    region = rules.get("region") if isinstance(rules.get("region"), dict) else {}
    ctx = PlanContext(
        weights=weights,
        available_from=available_from,
        crop_names={k: v.name for k, v in catalog.items() if v.name},
        pool_medians=pool_medians(list(profiles.values())),
        pool_size=len(profiles),
        history_missing=not history,
        soil_weak=not soil or soil.get("source", "unknown") != "lab",
        irrigated=bool(constraints.get("irrigated")),
        scenario_status=scenario_status,
        scenario_text=scenario_text,
        plan_numbers={s.sequence: i + 1 for i, s in enumerate(selections)},
        requested_criteria=requested_criteria,
        previous_crop_source=previous_source,
        provisional_rules=bool(region.get("provisional")) or str(region.get("id", "")).startswith("ro-romania-provisional-"),
    )

    baseline_plan = None
    if current is not None:
        baseline_plan = _build_current_baseline(continuation, current, weights, known_ids, reference, excluded, ctx, data_gaps)
        if baseline_plan is not None:
            ctx.current_score = current.score

    plans = []
    for number, selection in enumerate(selections, start=1):
        cand = eligible[selection.sequence]
        plans.append(_build_plan(number, selection, cand, pareto[selection.sequence], robustness.get(selection.sequence), ctx))
        data_gaps.extend(cand.evaluation.data_gaps)
        if cand.unresolved_ids:
            data_gaps.append(
                f"Option {number}: the evaluator cited sources missing from the source list ({', '.join(cand.unresolved_ids)}); they were omitted."
            )
    shown = [eligible[s.sequence].evaluation for s in selections] + ([current.evaluation] if baseline_plan is not None else [])
    for evaluation in shown:
        assumptions.extend(evaluation.assumptions)
    if not plans and evaluated:
        # Explain the empty result with what P3 reported for every evaluated sequence
        # (environment-level reasons such as missing weather), not per-sequence noise.
        common = [g for g in evaluated[0].evaluation.data_gaps if all(g in c.evaluation.data_gaps for c in evaluated)]
        data_gaps.extend(common)
    cited = {i for p in plans for i in p["source_ids"]}
    if baseline_plan is not None:
        cited |= set(baseline_plan["source_ids"])
    extra = [s for s in evaluation_sources if s["id"] in cited]
    return finish(plans, _merge_sources(base_sources, extra), fixture, baseline_plan)


def _build_current_baseline(continuation, current: Candidate, weights, known_ids, reference, excluded, ctx, data_gaps):
    """Contract `baseline`, or None (with a data gap) when P3 cannot support it.

    Infeasible rotations are shown with their violations, but only if P3 supplied a
    temporally valid calendar and at least one resolvable source: calendars and sources
    are never fabricated.
    """
    evaluation = current.evaluation
    cycle_text = " → ".join(crop_label(ctx.crop_names, c) for c in continuation.cycle)
    _resolve_sources(current, weights, known_ids)
    problem = None
    if evaluation.feasibility == UNKNOWN:
        problem = "the evaluator could not establish its feasibility"
    elif evaluation.calendar is None:
        problem = "the evaluator returned no crop calendar for it"
    elif validate_calendar(evaluation.calendar, evaluation.rotation, ctx.available_from):
        problem = "the evaluator's crop calendar for it is not temporally valid after the field availability date"
    elif not current.source_ids:
        problem = "the evaluator cited no verifiable source for it"
    if problem:
        message = f"Your current rotation ({cycle_text}) could not be shown for comparison: {problem}."
        if evaluation.violations:
            message += " It breaks these crop rotation rules: " + join_sentences(evaluation.violations)
        data_gaps.append(message)
        data_gaps.extend(evaluation.data_gaps)  # P3's own reason, e.g. a crop without rules
        return None
    robustness = None
    if reference and current.sequence in reference:
        r = reference[current.sequence]
        robustness = CandidateRobustness(
            reference_status="feasible" if r.status == FEASIBLE else r.status,
            reference_rank=None,
            scenario_rank=None,
            reference_eligible_count=0,
            deltas=criterion_deltas(evaluation, r.evaluation),
        )
    excluded_in = sorted(set(current.sequence) & set(excluded))
    texts = build_current_rotation_texts(continuation, evaluation, current.score, robustness, excluded_in, ctx)
    data_gaps.extend(evaluation.data_gaps)
    if current.unresolved_ids:
        data_gaps.append(
            f"Current rotation: the evaluator cited sources missing from the source list ({', '.join(current.unresolved_ids)}); they were omitted."
        )
    return {
        "id": "baseline",
        "label": texts["label"],
        "steps": _steps(evaluation, ctx),
        "benefits": texts["benefits"],
        "tradeoffs": texts["tradeoffs"],
        "explanation": texts["explanation"],
        "confidence": texts["confidence"],
        "source_ids": list(current.source_ids),
        "scores": plan_scores(evaluation),
        "local_checks": texts["local_checks"],
        "violations": texts["violations"],
        **_replay_field(evaluation),
    }


def _build_plan(number, selection, cand: Candidate, pareto: ParetoInfo, robustness, ctx: PlanContext) -> dict:
    evaluation, score = cand.evaluation, cand.score
    confidence, reasons = assess_confidence(evaluation, score, ctx, robustness)
    texts = build_texts(number, selection, evaluation, score, pareto, robustness, ctx)
    checks = local_checks(evaluation, ctx)
    return {
        "id": f"plan-{number}-" + "-".join(cand.sequence),
        "label": texts["label"],
        "steps": _steps(evaluation, ctx),
        "benefits": texts["benefits"],
        "tradeoffs": texts["tradeoffs"],
        "explanation": build_explanation(selection, evaluation, score, pareto, confidence, reasons, ctx, checks),
        "confidence": confidence,
        "source_ids": list(cand.source_ids),
        "scores": plan_scores(evaluation),
        "local_checks": checks,
        **_replay_field(evaluation),
    }


def _replay_field(evaluation: Evaluation) -> dict:
    """Contract `plan.replay`: P3's per-season results, passed through unchanged."""
    return {"replay": [dict(season) for season in evaluation.replay]} if evaluation.replay else {}
