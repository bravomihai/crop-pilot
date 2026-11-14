"""P4 orchestration: generate → evaluate (P3) → classify → rank → Pareto → select → explain."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .config import CRITERIA, PLAN_COUNT, SEQUENCE_LENGTH, RecommenderConfig
from .evaluation import FEASIBLE, INFEASIBLE, UNKNOWN, Evaluation, parse_evaluation, valid_source
from .explanations import (
    PlanContext,
    assess_confidence,
    build_explanation,
    build_texts,
    pool_medians,
    weights_text,
)
from .generation import crop_catalog, generate_candidates
from .pareto import ParetoInfo, pareto_analysis
from .ranking import Score, normalize_priorities, rank, score_evaluation
from .scenarios import (
    COMPUTED,
    NOT_REQUESTED,
    UNSUPPORTED,
    CandidateRobustness,
    baseline_request,
    criterion_deltas,
    is_baseline,
    scenario_of,
)
from .selection import select_diverse
from .validation import history_issues, validate_calendar

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

    @property
    def status(self) -> str:
        return "complete" if len(self.plans) == PLAN_COUNT else "limited" if self.plans else "insufficient_data"


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


def _score_and_filter(candidates: dict, weights, known_ids: set, config: RecommenderConfig) -> None:
    for cand in candidates.values():
        if cand.status != FEASIBLE:
            continue
        cand.score = score_evaluation(cand.evaluation, weights)
        cited = _cited_ids(cand.evaluation, cand.score)
        cand.source_ids = tuple(sorted({i for i in cited if i in known_ids}))
        cand.unresolved_ids = tuple(sorted({i for i in cited if i not in known_ids}))
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


def _dedupe(items) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


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
    available_from = date.fromisoformat(request["available_from"])
    constraints = request.get("constraints") or {}
    excluded = set(constraints.get("excluded_crops") or [])
    history = request.get("history") or []
    soil = request.get("soil") or {}
    temp, rain = scenario_of(request)
    scenario_requested = not is_baseline(request)
    scenario_text = (
        f"the hypothetical scenario of {temp:+.1f} °C and {rain:+.0f}% precipitation" if scenario_requested else None
    )

    base_sources = _merge_sources(environment.get("sources") or [], rules.get("sources") or [])
    assumptions = [
        "Each plan contains three successive main crops; this does not mean three years, and the plan does not repeat automatically.",
        f"Priorities were normalized to: {weights_text(weights)}.",
        "Criterion scores (0–1) come from the P3 evaluator; they are not yields, profits or probabilities.",
        "Unknown values are not replaced with zero or an average value; the score becomes an interval instead.",
    ]
    if scenario_text:
        assumptions.append(f"Requested {scenario_text}; this is a hypothetical assumption, not a NASA forecast.")
    data_gaps: list[str] = []
    if not history:
        data_gaps.append("No crop history was provided; compatibility with the previous crop cannot be verified.")
    if not soil or soil.get("source", "unknown") == "unknown":
        data_gaps.append("Soil properties are not known from a laboratory analysis or an estimate; the soil assessment depends on regional data.")

    catalog, catalog_issues = crop_catalog(rules)
    data_gaps.extend(catalog_issues)
    data_gaps.extend(history_issues(request, set(catalog)))
    diagnostics: dict = {"crops": sorted(catalog), "excluded": sorted(excluded)}

    def finish(plans, sources, fixture=False) -> RecommendationOutcome:
        if len(plans) < PLAN_COUNT:
            data_gaps.append(
                f"{len(plans)} feasible, documented plan(s) were found; the result was not padded with invented options."
            )
        return RecommendationOutcome(plans, sources, _dedupe(assumptions), _dedupe(data_gaps), diagnostics, fixture)

    candidate_set = generate_candidates(catalog, excluded, config.max_candidates)
    diagnostics.update(total_space=candidate_set.total_space, generated=len(candidate_set.candidates), truncated=candidate_set.truncated)
    if not candidate_set.candidates:
        data_gaps.append(
            "The regional rules offer no candidate crops after the exclusions were applied."
            if catalog
            else "The regional rules contain no candidate crops."
        )
        return finish([], base_sources)
    if candidate_set.truncated:
        data_gaps.append(
            f"The search space ({candidate_set.total_space} sequences) exceeds the limit of {config.max_candidates}; "
            "a deterministic sample was evaluated, so good plans may remain unexplored."
        )

    # Primary evaluation: the request as given (including any scenario).
    candidates = _evaluate_all(candidate_set.candidates, request, environment, rules, evaluate, available_from)
    evaluation_sources = [s for c in candidates.values() for s in c.evaluation.sources]
    all_sources = _merge_sources(base_sources, evaluation_sources)
    known_ids = {s["id"] for s in all_sources if valid_source(s)}
    _score_and_filter(candidates, weights, known_ids, config)
    fixture = any(c.evaluation.fixture for c in candidates.values())
    if fixture:
        assumptions.append("Evaluations come from a test (fixture) evaluator; they are not agronomic results.")

    # Scenario support and robustness.
    if not scenario_requested:
        scenario_status = NOT_REQUESTED
    elif all(c.evaluation.scenario_applied for c in candidates.values()):
        scenario_status = COMPUTED
    else:
        scenario_status = UNSUPPORTED
        data_gaps.append(
            "The evaluator did not confirm that the hypothetical scenario was applied; the ranking does not reflect the scenario and robustness was not computed."
        )
    diagnostics["scenario_status"] = scenario_status

    counts = _counts(candidates)
    diagnostics["counts"] = counts
    assumptions.append(
        f"Search: {len(candidates)} sequences evaluated from {len(candidate_set.crops)} available crops; "
        f"{counts[FEASIBLE]} feasible, {counts[INFEASIBLE]} infeasible, {counts[UNKNOWN]} with unknown feasibility, "
        f"{counts[CALENDAR_INVALID]} with an invalid calendar."
    )
    if counts[UNKNOWN]:
        data_gaps.append(f"{counts[UNKNOWN]} sequences could not be fully evaluated by P3 and were excluded; missing evidence is not treated as feasibility.")
    if counts[CALENDAR_INVALID]:
        data_gaps.append(f"{counts[CALENDAR_INVALID]} sequences had overlapping calendars or calendars incompatible with the field availability date and were excluded.")
    if counts["low_coverage"]:
        data_gaps.append(f"{counts['low_coverage']} feasible sequences had P3 scores for less than {config.min_coverage * 100:.0f}% of the priority weight and were not proposed.")
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
    if scenario_status == COMPUTED:
        baseline = _evaluate_all(candidate_set.candidates, baseline_request(request), environment, rules, evaluate, available_from)
        base_known = known_ids | {s["id"] for c in baseline.values() for s in c.evaluation.sources}
        _score_and_filter(baseline, weights, base_known, config)
        base_ranked = rank({seq: c.score for seq, c in baseline.items() if c.eligible})
        base_pos = {seq: i + 1 for i, seq in enumerate(base_ranked)}
        scen_pos = {seq: i + 1 for i, seq in enumerate(ranked)}
        for seq in eligible:
            b = baseline[seq]
            robustness[seq] = CandidateRobustness(
                baseline_status=b.status if b.eligible or b.status != FEASIBLE else "not_comparable",
                baseline_rank=base_pos.get(seq),
                scenario_rank=scen_pos[seq],
                baseline_eligible_count=len(base_ranked),
                deltas=criterion_deltas(candidates[seq].evaluation, b.evaluation),
            )
        diagnostics["baseline_counts"] = _counts(baseline)

    selections = select_diverse(ranked, scores, profiles, pareto, weights, config)
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
    )

    plans = []
    for number, selection in enumerate(selections, start=1):
        cand = eligible[selection.sequence]
        plans.append(_build_plan(number, selection, cand, pareto[selection.sequence], robustness.get(selection.sequence), ctx))
        data_gaps.extend(cand.evaluation.data_gaps)
        if cand.unresolved_ids:
            data_gaps.append(
                f"Option {number}: the evaluator cited sources missing from the source list ({', '.join(cand.unresolved_ids)}); they were omitted."
            )
    if plans:
        cited = {i for p in plans for i in p["source_ids"]}
        extra = [s for s in evaluation_sources if s["id"] in cited]
        all_sources = _merge_sources(base_sources, extra)
    else:
        all_sources = base_sources
    return finish(plans, all_sources, fixture)


def _build_plan(number, selection, cand: Candidate, pareto: ParetoInfo, robustness, ctx: PlanContext) -> dict:
    evaluation, score = cand.evaluation, cand.score
    steps = []
    for index, step in enumerate(evaluation.calendar):
        sowing_start = step.sowing_start
        reason = step.reason or "Window taken from the regional calendar supplied by the P3 evaluator."
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
    confidence, reasons = assess_confidence(evaluation, score, ctx, robustness)
    texts = build_texts(number, selection, evaluation, score, pareto, robustness, ctx)
    return {
        "id": f"plan-{number}-" + "-".join(cand.sequence),
        "label": texts["label"],
        "steps": steps,
        "benefits": texts["benefits"],
        "tradeoffs": texts["tradeoffs"],
        "explanation": build_explanation(selection, evaluation, score, pareto, confidence, reasons, ctx),
        "confidence": confidence,
        "source_ids": list(cand.source_ids),
    }
