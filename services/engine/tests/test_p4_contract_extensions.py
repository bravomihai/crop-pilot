"""P4 support for the optional contract fields added on main.

productivity priority, current_rotation → baseline, history[].source, and the plan fields
scores / local_checks / violations. Every evaluation comes from the SYNTHETIC evaluator in
tests/fake_evaluator.py; these tests check P4 logic and contract shape, not agronomy.
"""

import copy

import pytest

from fake_evaluator import FakeEvaluator, fake_rules
from fieldshift import pipeline
from fieldshift.contracts import example, validate
from fieldshift.recommender import PlanList, recommend, recommend_rotations
from fieldshift.recommender.ranking import normalize_priorities
from fieldshift.recommender.rotation import continue_rotation
from fieldshift.recommender.validation import ordered_history, validate_result_semantics

ENV = {"sources": [], "assumptions": [], "data_gaps": []}
STRONG_SOIL = {"texture": "loamy", "ph": 6.8, "source": "lab"}


def make_request(**changes):
    request = example("recommendation-request")
    request.update(copy.deepcopy(changes))
    return request


def strong(**changes):
    """Documented history + lab soil, so confidence differences come from the field under test."""
    base = {"history": [{"crop_id": "epsilon", "harvest_year": 2026, "source": "typed"}], "soil": STRONG_SOIL}
    base.update(changes)
    return make_request(**base)


def seqs(plans):
    return [tuple(s["crop_id"] for s in p["steps"]) for p in plans]


def real_like(**kwargs):
    # fixture=False only so the pipeline assembles a computed result; values stay synthetic.
    return FakeEvaluator(fixture=False, **kwargs)


# Old request format ---------------------------------------------------------------------


def test_old_request_format_is_unchanged_in_behaviour():
    request = make_request()
    assert "productivity" not in request["priorities"] and "current_rotation" not in request
    result = pipeline.computed_result(request, "old-format", ENV, fake_rules(), real_like())
    assert validate("recommendation-result", result) == []
    assert validate_result_semantics(result) == []
    assert "baseline" not in result and result["status"] == "complete"
    assert normalize_priorities(request["priorities"])["productivity"] == 0.0
    assert not any("productivity" in a.lower() for a in result["assumptions"])
    for plan in result["plans"]:
        assert "violations" not in plan
        assert set(plan["scores"]) == {"water", "soil", "climate", "productivity"}
        assert plan["local_checks"] and all(isinstance(c, str) for c in plan["local_checks"])


def test_old_request_ranking_ignores_productivity_scores():
    with_scores = recommend(make_request(), ENV, fake_rules(), FakeEvaluator())
    without = recommend(make_request(), ENV, fake_rules(), FakeEvaluator(missing=("productivity",)))
    assert seqs(with_scores.plans) == seqs(without.plans)


# Productivity --------------------------------------------------------------------------


def test_productivity_weight_changes_ranking_and_is_disclosed():
    prod = make_request(priorities={"water": 0, "soil": 0, "climate": 0, "productivity": 5})
    water = make_request(priorities={"water": 5, "soil": 0, "climate": 0, "productivity": 0})
    a = recommend(prod, ENV, fake_rules(), FakeEvaluator())
    b = recommend(water, ENV, fake_rules(), FakeEvaluator())
    assert seqs(a.plans)[0] != seqs(b.plans)[0]
    assert any("not a yield or profit forecast" in x for x in a.assumptions)
    assert "productivity 100%" in a.plans[0]["explanation"]
    assert normalize_priorities(prod["priorities"]) == {"water": 0.0, "soil": 0.0, "climate": 0.0, "productivity": 1.0}


def test_productivity_only_priority_is_valid_and_all_zero_is_not():
    normalize_priorities({"water": 0, "soil": 0, "climate": 0, "productivity": 2})
    with pytest.raises(ValueError):
        normalize_priorities({"water": 0, "soil": 0, "climate": 0, "productivity": 0})
    with pytest.raises(ValueError):
        normalize_priorities({"water": 1, "soil": 1, "climate": 1, "productivity": -1})


def test_missing_weighted_productivity_is_an_interval_and_null_score():
    request = strong(priorities={"water": 1, "soil": 1, "climate": 1, "productivity": 1})
    outcome = recommend(request, ENV, fake_rules(), real_like(missing=("productivity",)))
    plan = outcome.plans[0]
    assert plan["scores"]["productivity"] is None
    assert "between" in plan["explanation"] and plan["confidence"] == "low"


def test_requested_but_unweighted_productivity_lowers_confidence_only_when_requested():
    missing = real_like(missing=("productivity",))
    requested = strong(priorities={"water": 1, "soil": 1, "climate": 1, "productivity": 0})
    absent = strong()
    assert {p["confidence"] for p in recommend(requested, ENV, fake_rules(), missing).plans} == {"medium"}
    assert {p["confidence"] for p in recommend(absent, ENV, fake_rules(), missing).plans} == {"high"}


def test_productivity_takes_part_in_pareto_analysis():
    request = make_request(priorities={"water": 1, "soil": 0, "climate": 0, "productivity": 1})
    outcome = recommend(request, ENV, fake_rules(), FakeEvaluator())
    assert outcome.diagnostics["pareto_frontier"] >= 1
    only_water = recommend(make_request(priorities={"water": 1, "soil": 0, "climate": 0}), ENV, fake_rules(), FakeEvaluator())
    assert outcome.diagnostics["pareto_frontier"] != only_water.diagnostics["pareto_frontier"]


# history[].source ----------------------------------------------------------------------


@pytest.mark.parametrize("source", ["typed", "apia", "spray_records"])
def test_documented_history_sources_allow_high_confidence(source):
    request = strong(history=[{"crop_id": "epsilon", "harvest_year": 2026, "source": source}])
    plans = recommend(request, ENV, fake_rules(), real_like()).plans
    assert {p["confidence"] for p in plans} == {"high"}


def test_satellite_history_lowers_confidence_and_asks_for_confirmation():
    request = strong(history=[{"crop_id": "epsilon", "harvest_year": 2026, "source": "satellite"}])
    outcome = recommend(request, ENV, fake_rules(), real_like())
    assert {p["confidence"] for p in outcome.plans} == {"medium"}
    assert any("satellite classification" in g for g in outcome.data_gaps)
    assert any("satellite classification" in c for c in outcome.plans[0]["local_checks"])


@pytest.mark.parametrize("entry", [{"crop_id": "epsilon", "harvest_year": 2026}, {"crop_id": "epsilon", "harvest_year": 2026, "source": "unknown"}])
def test_unknown_history_source_is_not_assumed_wrong(entry):
    outcome = recommend(strong(history=[entry]), ENV, fake_rules(), real_like())
    assert {p["confidence"] for p in outcome.plans} == {"high"}
    assert any("source of the crop history was not stated" in c for c in outcome.plans[0]["local_checks"])


def test_only_the_most_recent_history_entry_sets_the_previous_crop_source():
    history = [
        {"crop_id": "alpha", "harvest_year": 2026, "source": "satellite"},
        {"crop_id": "epsilon", "harvest_year": 2024, "source": "apia"},
    ]
    assert ordered_history(history)[-1]["crop_id"] == "alpha"
    outcome = recommend(strong(history=history), ENV, fake_rules(), real_like())
    assert {p["confidence"] for p in outcome.plans} == {"medium"}
    undated = [{"crop_id": "alpha"}, {"crop_id": "beta", "harvest_year": 2020}]
    assert ordered_history(undated) == undated  # mixed dating: farmer's order is kept


# current_rotation → baseline -----------------------------------------------------------


def test_continue_rotation_alignment_rules():
    hist = lambda *crops: [{"crop_id": c} for c in crops]
    full = continue_rotation(["maize", "winter_wheat"], hist("maize", "winter_wheat", "maize"))
    assert full.sequence == ("winter_wheat", "maize", "winter_wheat") and full.aligned and full.matched == 3
    none = continue_rotation(["maize", "winter_wheat"], [])
    assert none.sequence == ("maize", "winter_wheat", "maize") and not none.aligned
    foreign = continue_rotation(["maize", "winter_wheat"], hist("sunflower"))
    assert not foreign.aligned
    ambiguous = continue_rotation(["maize", "maize", "wheat"], hist("maize"))
    assert ambiguous.ambiguous and ambiguous.sequence == ("maize", "wheat", "maize")
    resolved = continue_rotation(["maize", "maize", "wheat"], hist("wheat", "maize"))
    assert not resolved.ambiguous and resolved.sequence == ("maize", "wheat", "maize")
    assert continue_rotation(["pea"], []).sequence == ("pea", "pea", "pea")


def test_baseline_is_returned_separately_and_not_counted():
    request = strong(history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "apia"}], current_rotation=["alpha", "beta"])
    evaluator = real_like()
    result = pipeline.computed_result(request, "rot-1", ENV, fake_rules(), evaluator)
    assert validate("recommendation-result", result) == []
    assert validate_result_semantics(result) == []
    baseline = result["baseline"]
    assert baseline["id"] == "baseline" and result["status"] == "complete" and len(result["plans"]) == 3
    assert seqs([baseline]) == [("beta", "alpha", "beta")]
    assert ("beta", "alpha", "beta") in [r for r, _ in evaluator.calls]  # evaluated by P3
    assert baseline["violations"] == []
    assert set(baseline["scores"]) == {"water", "soil", "climate", "productivity"}
    assert baseline["local_checks"] and set(baseline["source_ids"]) <= {s["id"] for s in result["sources"]}
    assert "not a recommendation" in baseline["explanation"]
    assert all("current rotation" in " ".join(p["benefits"] + p["tradeoffs"]) for p in result["plans"])


def test_infeasible_current_rotation_is_disclosed_with_violations():
    seq = ("beta", "alpha", "beta")
    request = strong(history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "typed"}], current_rotation=["alpha", "beta"])
    evaluator = real_like(infeasible_with_calendar=[seq])
    result = pipeline.computed_result(request, "rot-2", ENV, fake_rules(), evaluator)
    assert validate("recommendation-result", result) == [] and validate_result_semantics(result) == []
    baseline = result["baseline"]
    assert baseline["violations"] == ["synthetic: rule broken"]
    assert baseline["tradeoffs"][0].startswith("Breaks a crop rotation rule")
    assert "breaks 1 crop rotation rule" in baseline["explanation"]
    assert seq not in seqs(result["plans"])  # never recommended
    assert all("violations" not in p for p in result["plans"])


def test_current_rotation_without_calendar_is_omitted_and_violations_reported():
    request = strong(current_rotation=["alpha"])  # alpha, alpha, alpha: synthetic repeat rule
    outcome = recommend(request, ENV, fake_rules(), real_like())
    assert outcome.baseline is None
    gap = next(g for g in outcome.data_gaps if "current rotation" in g)
    assert "no crop calendar" in gap and "same crop twice in a row" in gap


def test_current_rotation_with_unknown_feasibility_is_omitted():
    seq = ("beta", "alpha", "beta")
    request = strong(history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "typed"}], current_rotation=["alpha", "beta"])
    outcome = recommend(request, ENV, fake_rules(), real_like(unknown_for=[seq]))
    assert outcome.baseline is None
    assert any("could not establish its feasibility" in g for g in outcome.data_gaps)
    assert outcome.status == "complete"


def test_current_rotation_without_sources_is_omitted():
    seq = ("beta", "alpha", "beta")
    inner = real_like()

    def evaluate(rotation, request, environment, rules):
        result = inner(rotation, request, environment, rules)
        if tuple(rotation) == seq:
            result["source_ids"] = []
            for c in result["criteria"].values():
                c["source_ids"] = []
            for step in result["calendar"]:
                step["source_ids"] = []
        return result

    request = strong(history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "typed"}], current_rotation=["alpha", "beta"])
    outcome = recommend(request, ENV, fake_rules(), evaluate)
    assert outcome.baseline is None and any("no verifiable source" in g for g in outcome.data_gaps)


def test_current_rotation_position_assumed_without_history():
    outcome = recommend(make_request(soil=STRONG_SOIL, current_rotation=["alpha", "beta"]), ENV, fake_rules(), real_like())
    baseline = outcome.baseline
    assert seqs([baseline]) == [("alpha", "beta", "alpha")]
    assert "continued from its first listed crop" in baseline["explanation"]
    assert any("comes next" in c for c in baseline["local_checks"])
    assert "position in the current rotation assumed" in baseline["explanation"]


def test_excluded_crops_still_appear_in_the_current_rotation_but_never_in_plans():
    request = strong(history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "typed"}], current_rotation=["alpha", "beta"])
    request["constraints"]["excluded_crops"] = ["beta"]
    evaluator = real_like()
    outcome = recommend(request, ENV, fake_rules(), evaluator)
    assert outcome.baseline is not None
    assert any("you excluded" in t for t in outcome.baseline["tradeoffs"])
    assert all("beta" not in s for s in seqs(outcome.plans))
    assert len(evaluator.calls) == 64 + 1  # 4 crops ** 3 candidates + the current rotation


def test_baseline_reuses_candidate_evaluation_when_possible():
    request = strong(history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "typed"}], current_rotation=["alpha", "beta"])
    evaluator = real_like()
    recommend(request, ENV, fake_rules(), evaluator)
    assert len(evaluator.calls) == 125


def test_scenario_and_current_rotation_comparisons_stay_distinct():
    request = strong(
        history=[{"crop_id": "alpha", "harvest_year": 2026, "source": "typed"}],
        current_rotation=["alpha", "beta"],
        scenario={"temp_change_c": 2, "rain_change_pct": -10},
    )
    outcome = recommend(request, ENV, fake_rules(), real_like(scenario_aware=True))
    for plan in outcome.plans + [outcome.baseline]:
        text = " ".join(plan["benefits"] + plan["tradeoffs"]) + plan["explanation"]
        assert "baseline" not in text.lower()
        assert "current climate" in text
    baseline_text = " ".join(outcome.baseline["tradeoffs"] + outcome.baseline["benefits"])
    assert "rank" not in baseline_text  # the current rotation is never ranked
    assert any("current rotation" in t for p in outcome.plans for t in p["benefits"] + p["tradeoffs"])


def test_full_contract_example_request_runs_end_to_end():
    request = example("recommendation-request.full")
    rules = fake_rules()
    rules["crops"] += [{"id": "maize", "name": "Maize (synthetic)"}, {"id": "winter_wheat", "name": "Winter wheat (synthetic)"}]

    def evaluate(rotation, req, environment, r):
        if set(rotation) & {"maize", "winter_wheat"}:  # the fake evaluator has no data for them
            return {"feasibility": "unknown", "fixture": False, "scenario_applied": True}
        return real_like(scenario_aware=True)(rotation, req, environment, r)

    result = pipeline.computed_result(request, "full-example", ENV, rules, evaluate)
    assert validate("recommendation-result", result) == [] and validate_result_semantics(result) == []
    assert "baseline" not in result  # unknown feasibility: omitted, not invented
    # Display names from the rules, not crop IDs (full-stack audit).
    assert any(
        "Your current rotation (Maize (synthetic) → Winter wheat (synthetic)) could not be shown" in g
        for g in result["data_gaps"]
    )


# Plan fields and validator --------------------------------------------------------------


def test_scores_use_null_for_unknown_and_include_evaluator_local_checks():
    outcome = recommend(make_request(), ENV, fake_rules(), FakeEvaluator(missing=("soil",), local_checks=["check drainage"]))
    plan = outcome.plans[0]
    assert plan["scores"]["soil"] is None and plan["scores"]["water"] is not None
    assert "check drainage" in plan["local_checks"]


def test_semantic_validator_matches_new_zod_rules():
    result = example("recommendation-result.full")
    assert validate_result_semantics(result) == []
    broken = copy.deepcopy(result)
    broken["plans"][0]["violations"] = ["x"]
    broken["baseline"]["source_ids"] = ["missing"]
    broken["baseline"]["steps"][0]["order"] = 2
    errors = validate_result_semantics(broken)
    assert "Recommended plans cannot break agronomic rules." in errors
    assert "Unknown source reference in baseline." in errors
    assert "Baseline steps must be ordered 1, 2, 3." in errors
    allowed = copy.deepcopy(result)
    allowed["baseline"]["violations"] = ["the current rotation may break rules"]
    assert validate_result_semantics(allowed) == []


def test_recommend_rotations_returns_plain_compatible_plan_list():
    plans = recommend_rotations(make_request(), ENV, fake_rules(), FakeEvaluator())
    assert isinstance(plans, list) and isinstance(plans, PlanList)
    assert plans == plans.outcome.plans and len(plans) == 3
