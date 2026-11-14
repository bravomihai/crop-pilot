"""P4 algorithm tests with a SYNTHETIC evaluator (tests/fake_evaluator.py).

These tests verify generation, filtering, ranking, Pareto analysis, selection, calendar
checks, explanations and pipeline assembly. They do NOT validate agronomy: every crop,
calendar and score comes from a fake P3 evaluator.
"""

import copy
from datetime import date

import pytest

from fake_evaluator import FAKE_SOURCE, FakeEvaluator, fake_calendar, fake_rules
from fieldshift import pipeline
from fieldshift.contracts import example, validate
from fieldshift.recommender import RecommenderConfig, recommend, recommend_rotations
from fieldshift.recommender.evaluation import CalendarStep, Evaluation, Criterion, parse_evaluation
from fieldshift.recommender.generation import crop_catalog, generate_candidates
from fieldshift.recommender.pareto import (
    DOMINATED,
    NONDOMINATED,
    UNDETERMINED,
    dominates,
    pareto_analysis,
)
from fieldshift.recommender.ranking import normalize_priorities, rank, score_evaluation
from fieldshift.recommender.selection import (
    DIVERSE,
    SCORE_GAP,
    select_diverse,
    sequence_distance,
)
from fieldshift.recommender.pareto import ParetoInfo
from fieldshift.recommender.validation import validate_calendar, validate_result_semantics

ENV = {"sources": [], "assumptions": [], "data_gaps": []}


def make_request(**changes):
    request = example("recommendation-request")
    for key, value in changes.items():
        request[key] = value
    return request


def only(allowed, inner=None):
    """Synthetic evaluator: rotations outside `allowed` are infeasible."""
    inner = inner or FakeEvaluator(forbid_repeat=False)
    allowed = {tuple(a) for a in allowed}

    def evaluate(rotation, request, environment, rules):
        if tuple(rotation) not in allowed:
            return {"feasibility": "infeasible", "violations": ["synthetic"], "fixture": inner.fixture}
        return inner(rotation, request, environment, rules)

    return evaluate


def sequences(plans):
    return [tuple(s["crop_id"] for s in p["steps"]) for p in plans]


# 1. Candidate generation --------------------------------------------------------------


def test_generation_enumerates_ordered_triples_deterministically():
    result = generate_candidates(["c", "a", "b"])
    assert result.total_space == 27 and len(result.candidates) == 27
    assert result.candidates == tuple(sorted(result.candidates))
    assert ("a", "a", "a") in result.candidates and ("c", "b", "a") in result.candidates
    assert not result.truncated


def test_generation_truncation_is_bounded_deterministic_and_reported():
    crops = [f"crop_{i}" for i in range(20)]  # 8000 sequences
    first = generate_candidates(crops, max_candidates=500)
    second = generate_candidates(list(reversed(crops)), max_candidates=500)
    assert first.truncated and first.total_space == 8000
    assert len(first.candidates) == 500 and first.candidates == second.candidates
    # The sample is not biased toward alphabetically early first crops.
    assert len({c[0] for c in first.candidates}) == 20


def test_catalog_derives_crops_from_rules_only():
    catalog, issues = crop_catalog(fake_rules(["alpha", "beta"]))
    assert sorted(catalog) == ["alpha", "beta"] and not issues
    catalog, issues = crop_catalog({"crops": {"x": {"name": "X"}, "Bad Id": {}}})
    assert sorted(catalog) == ["x"] and issues
    assert crop_catalog({})[0] == {}


# 2./3. Exactly three crops and duplicate elimination -----------------------------------


def test_every_plan_has_exactly_three_ordered_steps():
    outcome = recommend(make_request(), ENV, fake_rules(), FakeEvaluator())
    assert outcome.status == "complete"
    for plan in outcome.plans:
        assert [s["order"] for s in plan["steps"]] == [1, 2, 3]


def test_duplicates_are_eliminated():
    assert len(generate_candidates(["a", "a", "b"]).candidates) == 8
    rules = fake_rules(["alpha", "beta"])
    rules["crops"] += [{"id": "alpha", "name": "duplicate"}]
    evaluator = FakeEvaluator(forbid_repeat=False)
    outcome = recommend(make_request(), ENV, rules, evaluator)
    assert len(evaluator.calls) == 8 == len(set(r for r, _ in evaluator.calls))
    assert len(set(sequences(outcome.plans))) == len(outcome.plans)


# 4. Excluded crops ----------------------------------------------------------------------


def test_excluded_crops_are_never_generated_or_evaluated():
    request = make_request()
    request["constraints"]["excluded_crops"] = ["gamma", "alpha"]
    evaluator = FakeEvaluator()
    outcome = recommend(request, ENV, fake_rules(), evaluator)
    assert all(not {"gamma", "alpha"} & set(r) for r, _ in evaluator.calls)
    assert all(not {"gamma", "alpha"} & set(s) for s in sequences(outcome.plans))


# 5./6. Feasibility filtering and empty sets -------------------------------------------


def test_infeasible_unknown_and_bad_calendar_candidates_are_rejected():
    bad_calendar = fake_calendar(("alpha", "beta", "gamma"), date(2027, 3, 1))
    bad_calendar[1]["sowing_window"]["start"] = bad_calendar[0]["harvest_window"]["start"]
    override = {
        "feasibility": "feasible",
        "fixture": True,
        "criteria": {n: {"score": 1.0, "basis": "derived", "source_ids": ["fake-p3"]} for n in ("water", "soil", "climate")},
        "calendar": bad_calendar,
        "source_ids": ["fake-p3"],
    }
    evaluator = FakeEvaluator(
        unknown_for=[("gamma", "alpha", "beta")], overrides={("alpha", "beta", "gamma"): override}
    )
    outcome = recommend(make_request(), ENV, fake_rules(), evaluator)
    plans = sequences(outcome.plans)
    assert ("alpha", "beta", "gamma") not in plans  # perfect scores but overlapping calendar
    assert ("gamma", "alpha", "beta") not in plans
    assert all(a != b for s in plans for a, b in zip(s, s[1:]))
    counts = outcome.diagnostics["counts"]
    assert counts["calendar_invalid"] == 1 and counts["unknown"] == 1 and counts["infeasible"] > 0


def test_feasible_with_violations_is_treated_as_infeasible():
    evaluation = parse_evaluation({"feasibility": "feasible", "violations": ["x"]}, ("a", "b", "c"))
    assert evaluation.feasibility == "infeasible"
    assert parse_evaluation({"criteria": {}}, ("a", "b", "c")).feasibility == "unknown"
    assert parse_evaluation(None, ("a", "b", "c")).feasibility == "unknown"


def test_empty_and_insufficient_candidate_sets():
    request = make_request()
    request["constraints"]["excluded_crops"] = sorted(fake_rules()["crops"][i]["id"] for i in range(5))
    evaluator = FakeEvaluator()
    outcome = recommend(request, ENV, fake_rules(), evaluator)
    assert outcome.status == "insufficient_data" and outcome.plans == [] and not evaluator.calls
    assert recommend(make_request(), ENV, {}, FakeEvaluator()).status == "insufficient_data"
    all_unknown = FakeEvaluator(unknown_for=generate_candidates(sorted(fake_rules_ids())).candidates)
    assert recommend(make_request(), ENV, fake_rules(), all_unknown).plans == []


def fake_rules_ids():
    return [c["id"] for c in fake_rules()["crops"]]


# 7./8. Priorities -----------------------------------------------------------------------


def test_priority_normalization():
    weights = normalize_priorities({"water": 3, "soil": 1, "climate": 0})
    assert weights == {"water": 0.75, "soil": 0.25, "climate": 0.0, "productivity": 0.0}
    assert sum(normalize_priorities({"water": 5, "soil": 5, "climate": 5}).values()) == pytest.approx(1)


@pytest.mark.parametrize(
    "priorities",
    [
        {"water": 0, "soil": 0, "climate": 0},
        {"water": -1, "soil": 1, "climate": 1},
        {"water": True, "soil": 1, "climate": 1},
        {"water": 1, "soil": 1},
    ],
)
def test_invalid_or_all_zero_priorities_are_rejected(priorities):
    with pytest.raises(ValueError):
        normalize_priorities(priorities)
    with pytest.raises(ValueError):
        recommend(make_request(priorities=priorities), ENV, fake_rules(), FakeEvaluator())


def test_priorities_change_the_top_plan():
    water = recommend(make_request(priorities={"water": 5, "soil": 0, "climate": 0}), ENV, fake_rules(), FakeEvaluator())
    soil = recommend(make_request(priorities={"water": 0, "soil": 5, "climate": 0}), ENV, fake_rules(), FakeEvaluator())
    assert sequences(water.plans)[0] != sequences(soil.plans)[0]


# 9. Missing objective scores ------------------------------------------------------------


def _evaluation(scores):
    return Evaluation(
        ("a", "b", "c"),
        "feasible",
        criteria={n: Criterion(n, s, "derived", None, ("s",)) for n, s in scores.items()},
    )


def test_missing_scores_produce_interval_not_substitute():
    weights = normalize_priorities({"water": 1, "soil": 1, "climate": 2})
    score = score_evaluation(_evaluation({"water": 0.8, "soil": None, "climate": 0.5}), weights)
    assert score.lower == pytest.approx(0.25 * 0.8 + 0.5 * 0.5)
    assert score.upper == pytest.approx(score.lower + 0.25)
    assert score.coverage == pytest.approx(0.75) and score.missing == ("soil",)
    assert score.value is None
    # Zero-weight criteria never count as missing.
    zero = normalize_priorities({"water": 1, "soil": 0, "climate": 0})
    assert score_evaluation(_evaluation({"water": 0.4, "soil": None, "climate": None}), zero).complete


def test_partial_evidence_cannot_outrank_by_luck():
    weights = normalize_priorities({"water": 1, "soil": 1, "climate": 1})
    complete = score_evaluation(_evaluation({"water": 0.6, "soil": 0.6, "climate": 0.6}), weights)
    partial = score_evaluation(_evaluation({"water": 0.9, "soil": 0.9, "climate": None}), weights)
    assert rank({("x",): complete, ("y",): partial}) == [("x",), ("y",)]


def test_low_coverage_candidates_are_not_proposed():
    evaluator = FakeEvaluator(missing=("water", "soil"))
    outcome = recommend(make_request(), ENV, fake_rules(), evaluator)
    assert outcome.status == "insufficient_data"
    assert outcome.diagnostics["counts"]["low_coverage"] > 0
    partial = recommend(make_request(), ENV, fake_rules(), FakeEvaluator(missing=("soil",)))
    assert partial.plans and all(p["confidence"] == "low" for p in partial.plans)
    assert any("not known for this field" in t for t in partial.plans[0]["tradeoffs"])


# 10. Determinism ------------------------------------------------------------------------


def test_identical_inputs_give_identical_outputs():
    a = recommend(make_request(), ENV, fake_rules(), FakeEvaluator())
    b = recommend(make_request(), ENV, fake_rules(), FakeEvaluator())
    rules = fake_rules()
    rules["crops"].reverse()
    c = recommend(make_request(), ENV, rules, FakeEvaluator())
    assert a.plans == b.plans == c.plans
    assert a.data_gaps == b.data_gaps and a.assumptions == b.assumptions


# 11. Pareto -----------------------------------------------------------------------------


def test_pareto_dominance_rules():
    objs = ("water", "soil")
    assert dominates({"water": 0.8, "soil": 0.5}, {"water": 0.7, "soil": 0.5}, objs) is True
    assert dominates({"water": 0.8, "soil": 0.4}, {"water": 0.7, "soil": 0.5}, objs) is False
    assert dominates({"water": 0.5, "soil": 0.5}, {"water": 0.5, "soil": 0.5}, objs) is False
    assert dominates({"water": 0.9, "soil": None}, {"water": 0.1, "soil": 0.1}, objs) is None
    profiles = {
        "a": {"water": 0.9, "soil": 0.2},
        "b": {"water": 0.2, "soil": 0.9},
        "c": {"water": 0.1, "soil": 0.1},
        "d": {"water": 1.0, "soil": None},
    }
    info = pareto_analysis(profiles, objs)
    assert info["a"].status == info["b"].status == NONDOMINATED
    assert info["c"].status == DOMINATED and set(info["c"].dominated_by) == {"a", "b"}
    assert info["d"].status == UNDETERMINED


def test_pruned_pareto_matches_naive_pairwise_definition():
    import random

    rng = random.Random(7)
    objs = ("water", "soil", "climate")
    profiles = {
        i: {o: round(rng.random(), 1) if rng.random() > 0.1 else None for o in objs} for i in range(200)
    }
    info = pareto_analysis(profiles, objs)
    for key, p in profiles.items():
        if any(p[o] is None for o in objs):
            assert info[key].status == UNDETERMINED
            continue
        naive = tuple(sorted(k for k, q in profiles.items() if k != key and dominates(q, p, objs)))
        assert info[key].dominated_by == naive
        assert info[key].status == (DOMINATED if naive else NONDOMINATED)


# 12. Diverse selection ------------------------------------------------------------------


def _scores(values):
    weights = {"water": 1.0, "soil": 0.0, "climate": 0.0}
    scores, profiles = {}, {}
    for seq, v in values.items():
        scores[seq] = score_evaluation(_evaluation({"water": v, "soil": None, "climate": None}), weights)
        profiles[seq] = {"water": v, "soil": None, "climate": None}
    return scores, profiles, weights


def test_diverse_selection_skips_near_duplicates():
    values = {
        ("a", "b", "c"): 0.90,
        ("a", "b", "d"): 0.89,  # differs in one position only
        ("a", "c", "b"): 0.88,  # same crops, reordered
        ("d", "e", "f"): 0.82,  # different crops, close score
        ("e", "f", "g"): 0.80,
    }
    scores, profiles, weights = _scores(values)
    ranked = rank(scores)
    pareto = pareto_analysis(profiles, ("water",))
    chosen = select_diverse(ranked, scores, profiles, pareto, weights, RecommenderConfig())
    assert [s.sequence for s in chosen][0] == ("a", "b", "c")
    assert ("d", "e", "f") in [s.sequence for s in chosen]
    assert ("a", "b", "d") not in [s.sequence for s in chosen]
    assert all(s.tier == DIVERSE for s in chosen[1:])
    assert sequence_distance(("a", "b", "c"), ("a", "b", "c")) == 0


def test_inferior_diverse_plan_is_disclosed_as_score_gap():
    values = {("a", "b", "c"): 0.9, ("a", "b", "d"): 0.88, ("x", "y", "z"): 0.3}
    scores, profiles, weights = _scores(values)
    chosen = select_diverse(rank(scores), scores, profiles, pareto_analysis(profiles, ("water",)), weights, RecommenderConfig())
    gap = next(s for s in chosen if s.sequence == ("x", "y", "z"))
    assert gap.tier == SCORE_GAP and gap.score_gap == pytest.approx(0.6)


def test_end_to_end_alternatives_are_distinct():
    outcome = recommend(make_request(), ENV, fake_rules(), FakeEvaluator())
    seqs = sequences(outcome.plans)
    assert len(set(seqs)) == 3
    assert all(sequence_distance(a, b) > 0 for i, a in enumerate(seqs) for b in seqs[i + 1 :])


# 13. Sources ----------------------------------------------------------------------------


def test_source_references_are_preserved_and_resolvable():
    outcome = recommend(make_request(), ENV, {"crops": fake_rules()["crops"]}, FakeEvaluator())
    ids = {s["id"] for s in outcome.sources}
    assert "fake-p3" in ids  # contributed by the evaluation, not the rules
    assert all(set(p["source_ids"]) <= ids and p["source_ids"] for p in outcome.plans)


def test_unknown_cited_sources_are_dropped_and_reported():
    inner = FakeEvaluator()

    def evaluate(rotation, request, environment, rules):
        result = inner(rotation, request, environment, rules)
        if result.get("feasibility") == "feasible":
            result["source_ids"] = ["fake-p3", "ghost"]
        return result

    outcome = recommend(make_request(), ENV, fake_rules(), evaluate)
    assert all("ghost" not in p["source_ids"] for p in outcome.plans)
    assert any("ghost" in g for g in outcome.data_gaps)


def test_plans_without_resolvable_sources_are_not_proposed():
    inner = FakeEvaluator()

    def evaluate(rotation, request, environment, rules):
        result = inner(rotation, request, environment, rules)
        result.pop("sources", None)
        return result

    outcome = recommend(make_request(), ENV, {"crops": fake_rules()["crops"]}, evaluate)
    assert outcome.plans == [] and outcome.diagnostics["counts"]["no_sources"] > 0


# 14. Confidence -------------------------------------------------------------------------


def _strong_request():
    request = make_request(history=[{"crop_id": "epsilon", "harvest_year": 2026}])
    request["soil"] = {"texture": "loamy", "ph": 6.8, "source": "lab"}
    return request


def test_confidence_levels_follow_evidence_rules():
    fixture = recommend(_strong_request(), ENV, fake_rules(), FakeEvaluator())
    assert all(p["confidence"] == "low" for p in fixture.plans)
    real_like = recommend(_strong_request(), ENV, fake_rules(), FakeEvaluator(fixture=False))
    assert all(p["confidence"] == "high" for p in real_like.plans)
    no_history = recommend(make_request(), ENV, fake_rules(), FakeEvaluator(fixture=False))
    assert all(p["confidence"] == "medium" for p in no_history.plans)
    for plan in real_like.plans:
        assert "not a probability of success" in plan["explanation"]


# 15./16. Calendar ------------------------------------------------------------------------


def _step(crop, s0, s1, h0, h1):
    d = date.fromisoformat
    return CalendarStep(crop, None, d(s0), d(s1), d(h0), d(h1))


def test_autumn_crops_cross_the_year_boundary():
    outcome = recommend(make_request(), ENV, fake_rules(), only([("gamma", "alpha", "beta")]))
    steps = outcome.plans[0]["steps"]
    assert steps[0]["sowing_window"]["start"].startswith("2027-10")
    assert steps[0]["harvest_window"]["start"].startswith("2028-07")
    assert steps[0]["harvest_window"]["end"] < steps[1]["sowing_window"]["start"]
    assert steps[1]["sowing_window"]["start"].startswith("2029-03")  # March 2028 already passed
    steps = (
        _step("a", "2027-10-01", "2027-10-31", "2028-07-01", "2028-07-31"),
        _step("b", "2028-09-15", "2028-10-15", "2029-06-01", "2029-06-30"),
        _step("c", "2029-07-05", "2029-07-20", "2029-10-01", "2029-10-15"),
    )
    assert validate_calendar(steps, ("a", "b", "c"), date(2027, 9, 1)) == []
    overlap = (steps[0], _step("b", "2028-07-15", "2028-10-15", "2029-06-01", "2029-06-30"), steps[2])
    assert validate_calendar(overlap, ("a", "b", "c"), date(2027, 9, 1))


def test_available_from_is_enforced():
    steps = (
        _step("a", "2027-03-01", "2027-03-31", "2027-07-01", "2027-07-31"),
        _step("b", "2027-10-01", "2027-10-31", "2028-07-01", "2028-07-31"),
        _step("c", "2028-09-01", "2028-09-30", "2029-06-01", "2029-06-30"),
    )
    assert validate_calendar(steps, ("a", "b", "c"), date(2027, 3, 15)) == []
    assert validate_calendar(steps, ("a", "b", "c"), date(2027, 4, 1))
    outcome = recommend(make_request(available_from="2027-03-15"), ENV, fake_rules(), FakeEvaluator())
    for plan in outcome.plans:
        assert plan["steps"][0]["sowing_window"]["start"] >= "2027-03-15"


def test_sowing_start_before_availability_is_clipped_with_note():
    inner = FakeEvaluator()

    def evaluate(rotation, request, environment, rules):
        result = inner(rotation, request, environment, rules)
        if result.get("feasibility") == "feasible" and rotation[0] == "alpha":
            result["calendar"][0]["sowing_window"]["start"] = "2027-02-01"
        return result

    outcome = recommend(make_request(), ENV, fake_rules(), evaluate)
    alpha = [p for p in outcome.plans if p["steps"][0]["crop_id"] == "alpha"]
    assert alpha and alpha[0]["steps"][0]["sowing_window"]["start"] == "2027-03-01"
    assert "field availability date" in alpha[0]["steps"][0]["reason"]


# 17. History ----------------------------------------------------------------------------


def test_crop_history_is_passed_to_p3_and_checked():
    request = make_request(history=[{"crop_id": "gamma", "harvest_year": 2026}])
    evaluator = FakeEvaluator()
    outcome = recommend(request, ENV, fake_rules(), evaluator)
    assert all(s[0] != "gamma" for s in sequences(outcome.plans))
    future = make_request(history=[{"crop_id": "unlisted", "harvest_year": 2030}])
    gaps = recommend(future, ENV, fake_rules(), FakeEvaluator()).data_gaps
    assert any("2030" in g for g in gaps) and any("unlisted" in g for g in gaps)
    assert any("No crop history was provided" in g for g in recommend(make_request(), ENV, fake_rules(), FakeEvaluator()).data_gaps)


def test_request_is_not_mutated_by_evaluator():
    request = make_request()
    original = copy.deepcopy(request)

    def evaluate(rotation, req, environment, rules):
        req["priorities"]["water"] = 0
        return FakeEvaluator()(rotation, req, environment, rules)

    recommend(request, ENV, fake_rules(), evaluate)
    assert request == original


# 18. Scenarios --------------------------------------------------------------------------


def test_scenario_triggers_reference_climate_reevaluation_of_same_candidates():
    request = make_request(scenario={"temp_change_c": 3, "rain_change_pct": -20})
    evaluator = FakeEvaluator(scenario_aware=True)
    outcome = recommend(request, ENV, fake_rules(), evaluator)
    scen = [r for r, s in evaluator.calls if s["temp_change_c"] == 3]
    base = [r for r, s in evaluator.calls if s["temp_change_c"] == 0]
    assert scen == base and len(scen) == 125
    assert outcome.diagnostics["scenario_status"] == "computed"
    assert any("hypothetical assumption, not a NASA forecast" in a for a in outcome.assumptions)
    assert any("current climate" in t for p in outcome.plans for t in p["tradeoffs"] + p["benefits"])
    reference = recommend(make_request(), ENV, fake_rules(), FakeEvaluator(scenario_aware=True))
    assert sequences(outcome.plans) != sequences(reference.plans)


def test_unsupported_scenario_is_reported_not_simulated():
    request = make_request(scenario={"temp_change_c": 2, "rain_change_pct": 0})
    evaluator = FakeEvaluator(scenario_aware=False)
    outcome = recommend(request, ENV, fake_rules(), evaluator)
    assert outcome.diagnostics["scenario_status"] == "unsupported"
    assert len(evaluator.calls) == 125  # no reference-climate pass
    assert any("did not confirm that the hypothetical scenario was applied" in g for g in outcome.data_gaps)


def test_no_scenario_means_single_pass():
    evaluator = FakeEvaluator()
    outcome = recommend(make_request(), ENV, fake_rules(), evaluator)
    assert len(evaluator.calls) == 125 and outcome.diagnostics["scenario_status"] == "not_requested"


# 19. Evaluator unavailable --------------------------------------------------------------


def test_unimplemented_evaluator_propagates():
    def unavailable(rotation, request, environment, rules):
        raise NotImplementedError("evaluator unavailable")

    with pytest.raises(NotImplementedError):
        recommend_rotations(make_request(), ENV, fake_rules(), unavailable)


def test_computed_mode_is_unavailable_until_p2_exists(monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "computed")
    monkeypatch.delenv("ENABLE_NASA_POWER", raising=False)
    with pytest.raises(NotImplementedError):  # P2 build_environment is still disabled
        pipeline.recommend(make_request(), "req-1")


def test_computed_mode_without_weather_never_invents_plans(monkeypatch):
    # Real P3 rules and evaluator, but an environment with no daily weather: water,
    # climate and productivity are unknown, so no plan has enough evidence.
    monkeypatch.setenv("ENGINE_MODE", "computed")
    monkeypatch.setattr(pipeline, "build_environment", lambda request: ENV)
    result = pipeline.recommend(make_request(), "req-1")
    assert not validate("recommendation-result", result)
    assert result["mode"] == "computed"
    assert result["status"] == "insufficient_data" and result["plans"] == []


def test_api_returns_503_in_computed_mode(monkeypatch):
    from fastapi.testclient import TestClient
    from fieldshift.api import app

    token = "t" * 40
    monkeypatch.setenv("INTERNAL_API_TOKEN", token)
    monkeypatch.setenv("ENGINE_MODE", "computed")
    monkeypatch.delenv("ENABLE_NASA_POWER", raising=False)
    response = TestClient(app).post(
        "/recommendations", json=make_request(), headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 503


def test_fixture_evaluations_cannot_back_computed_results():
    with pytest.raises(NotImplementedError):
        pipeline.computed_result(make_request(), "req-1", ENV, fake_rules(), FakeEvaluator())


# 20./21./22. Contract, status semantics and request_id -------------------------------


def test_computed_result_matches_contract_and_semantics():
    # fixture=False only to exercise result assembly; values remain synthetic.
    result = pipeline.computed_result(_strong_request(), "req-42", ENV, fake_rules(), FakeEvaluator(fixture=False))
    assert validate("recommendation-result", result) == []
    assert validate_result_semantics(result) == []
    assert result["request_id"] == "req-42" and result["mode"] == "computed"
    assert result["status"] == "complete"


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_status_semantics_for_each_plan_count(count):
    allowed = [("alpha", "beta", "gamma"), ("delta", "epsilon", "beta"), ("gamma", "delta", "alpha")][:count]
    inner = FakeEvaluator(forbid_repeat=False, fixture=False)
    result = pipeline.computed_result(make_request(), "req-s", ENV, fake_rules(), only(allowed, inner))
    expected = {0: "insufficient_data", 1: "limited", 2: "limited", 3: "complete"}[count]
    assert result["status"] == expected and len(result["plans"]) == count
    assert validate("recommendation-result", result) == []
    assert validate_result_semantics(result) == []
    if count < 3:
        assert any("not padded with invented options" in g for g in result["data_gaps"])


def test_request_id_is_preserved_in_both_modes(monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "demo")
    assert pipeline.recommend(make_request(), "abc-123")["request_id"] == "abc-123"
    result = pipeline.computed_result(make_request(), "xyz-789", ENV, fake_rules(), FakeEvaluator(fixture=False))
    assert result["request_id"] == "xyz-789"


def test_semantic_validator_matches_typescript_rules():
    result = example("recommendation-result")
    assert validate_result_semantics(result) == []
    broken = copy.deepcopy(result)
    broken["plans"][0]["steps"][1]["sowing_window"]["start"] = "2027-07-15"
    broken["plans"][1]["source_ids"] = ["missing"]
    broken["status"] = "limited"
    errors = validate_result_semantics(broken)
    assert "Crop windows overlap." in errors and "Unknown source reference." in errors
    assert "A limited result must contain one or two plans." in errors
