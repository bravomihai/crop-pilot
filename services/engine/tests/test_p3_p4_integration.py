"""Integration of the REAL P3 evaluator with the REAL P4 recommender and pipeline.

Environment: historical NASA POWER daily data for a Bărăgan test point
(tests/fixtures/environment-ro-south.json, 2005–2025), standing in for P2's data service.
Rules and scores come from fieldshift.evaluator (load_rules, evaluate); nothing here is a
fake evaluator or a synthetic score.

These tests verify that the modules work together and that P4 handles P3's evidence
honestly. Passing them is NOT agronomic validation: P3's calendars, successions and
thresholds are expert estimates awaiting agronomist review (docs/evaluator.md).
"""

from __future__ import annotations

import copy
import json
import re
import time
from functools import lru_cache
from pathlib import Path

import pytest

from fieldshift import pipeline
from fieldshift.contracts import validate
from fieldshift.evaluator import evaluate, load_rules
from fieldshift.recommender import recommend
from fieldshift.recommender.config import CRITERIA
from fieldshift.recommender.ranking import normalize_priorities
from fieldshift.recommender.validation import validate_result_semantics
from test_p4_english import romanian_hits

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "environment-ro-south.json"
BARAGAN = {"name": "Bărăgan test point", "latitude": 44.56, "longitude": 27.36}
OUTSIDE = {"name": "Outside covered zones", "latitude": 47.2, "longitude": 23.0}


@lru_cache(maxsize=1)
def _raw_environment() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def environment() -> dict:
    # A single shared object, as P2 would return per request; tests that alter the
    # environment make their own deep copy.
    return _env_singleton()


@lru_cache(maxsize=1)
def _env_singleton() -> dict:
    return json.loads(_raw_environment())


def make_request(**changes) -> dict:
    request = {
        "schema_version": "1.0",
        "location": dict(BARAGAN),
        "available_from": "2026-10-01",
        "crop_count": 3,
        "history": [{"crop_id": "maize", "harvest_year": 2026, "source": "typed"}],
        "priorities": {"water": 3, "soil": 3, "climate": 3},
        "constraints": {"irrigated": False, "excluded_crops": []},
        "scenario": {"temp_change_c": 0, "rain_change_pct": 0},
    }
    for key, value in changes.items():
        request[key] = copy.deepcopy(value)
    assert not validate("recommendation-request", request)
    return request


def run(request: dict, env: dict | None = None, request_id: str = "p3-p4") -> dict:
    env = environment() if env is None else env
    return pipeline.computed_result(request, request_id, env, load_rules(request["location"]), evaluate)


@lru_cache(maxsize=32)
def _cached(request_json: str) -> str:
    return json.dumps(run(json.loads(request_json)))


def cached_run(request: dict) -> dict:
    """Same request → reuse one pipeline run across tests (keeps the suite fast)."""
    return json.loads(_cached(json.dumps(request, sort_keys=True)))


def sequences(plans) -> list[tuple[str, ...]]:
    return [tuple(s["crop_id"] for s in p["steps"]) for p in plans]


def p3(sequence, request) -> dict:
    return evaluate(list(sequence), copy.deepcopy(request), environment(), load_rules(request["location"]))


def assert_valid(result: dict) -> None:
    assert validate("recommendation-result", result) == []
    assert validate_result_semantics(result) == []


def user_texts(result: dict) -> list[str]:
    texts = list(result["assumptions"]) + list(result["data_gaps"])
    for plan in result["plans"] + ([result["baseline"]] if "baseline" in result else []):
        texts += [plan["label"], plan["explanation"], *plan["benefits"], *plan["tradeoffs"]]
        texts += plan.get("local_checks", []) + plan.get("violations", []) + [s["reason"] for s in plan["steps"]]
    return texts


# 1–3, 12. Contract, shape and sources --------------------------------------------------


def test_full_result_is_contract_valid_with_three_distinct_three_crop_plans():
    result = cached_run(make_request())
    assert_valid(result)
    assert result["mode"] == "computed" and result["status"] == "complete"
    assert len(result["plans"]) == 3 and len(set(sequences(result["plans"]))) == 3
    rule_crops = {c["id"] for c in load_rules(BARAGAN)["crops"]}
    source_ids = {s["id"] for s in result["sources"]}
    for plan in result["plans"]:
        assert [s["order"] for s in plan["steps"]] == [1, 2, 3]
        assert {s["crop_id"] for s in plan["steps"]} <= rule_crops
        assert plan["source_ids"] and set(plan["source_ids"]) <= source_ids
        assert plan["steps"][0]["sowing_window"]["start"] >= "2026-10-01"
    assert "nasa-power" in source_ids and "fao56" in source_ids


# 4. No infeasible recommendation --------------------------------------------------------


def test_recommended_plans_are_feasible_according_to_p3():
    request = make_request()
    for seq in sequences(cached_run(request)["plans"]):
        evaluation = p3(seq, request)
        assert evaluation["feasibility"] == "feasible" and evaluation["violations"] == []


# 7, 8. Scores come from P3 unchanged; priorities applied to them ------------------------


def test_plan_scores_are_exactly_p3_scores_and_weighted_score_is_correct():
    request = make_request(priorities={"water": 4, "soil": 1, "climate": 2, "productivity": 3})
    result = cached_run(request)
    weights = normalize_priorities(request["priorities"])
    for plan in result["plans"]:
        criteria = p3(sequences([plan])[0], request)["criteria"]
        assert plan["scores"] == {n: criteria[n]["score"] for n in CRITERIA}
        expected = sum(weights[n] * criteria[n]["score"] for n in CRITERIA)
        assert f"an overall score of {expected * 100:.0f}/100" in plan["explanation"]


@pytest.mark.parametrize("criterion", ["water", "soil", "climate", "productivity"])
def test_single_priority_picks_the_best_p3_score_for_that_criterion(criterion):
    priorities = {"water": 0, "soil": 0, "climate": 0, criterion: 5}
    request = make_request(priorities=priorities)
    result = cached_run(request)
    best = sequences(result["plans"])[0]
    # Every feasible sequence P3 can evaluate, scored on the single criterion.
    crops = [c["id"] for c in load_rules(BARAGAN)["crops"]]
    scores = {}
    for a in crops:
        for b in crops:
            for c in crops:
                ev = p3((a, b, c), request)
                if ev["feasibility"] == "feasible" and ev["criteria"][criterion]["score"] is not None:
                    scores[(a, b, c)] = ev["criteria"][criterion]["score"]
    assert scores[best] == max(scores.values())


def test_changing_priorities_changes_the_recommendation():
    tops = {
        name: sequences(cached_run(make_request(priorities={"water": 0, "soil": 0, "climate": 0, name: 5}))["plans"])[0]
        for name in ("water", "soil", "productivity")
    }
    assert len(set(tops.values())) > 1


def test_unknown_scores_stay_null_and_are_never_filled_in():
    env = json.loads(_raw_environment())
    env["daily"] = [d for d in env["daily"] if d["date"] >= "2024-01-01"]  # too short to replay
    soil_only = make_request(priorities={"water": 0, "soil": 5, "climate": 0})
    result = run(soil_only, env)
    assert_valid(result)
    assert result["plans"], "soil is computed without weather, so soil-only plans are possible"
    for plan in result["plans"]:
        assert plan["scores"]["soil"] is not None
        assert plan["scores"]["water"] is None and plan["scores"]["climate"] is None
        assert plan["scores"]["productivity"] is None
    equal = run(make_request(), env)
    assert equal["status"] == "insufficient_data" and equal["plans"] == []
    assert any("not computed" in g for g in equal["data_gaps"])


# 10. Climate scenario reaches P3 and changes P4's comparison ----------------------------


def test_scenario_reaches_p3_and_is_compared_with_the_reference_climate():
    scenario = {"temp_change_c": 2, "rain_change_pct": -20}
    request = make_request(scenario=scenario)
    seen = []

    def recording(rotation, req, env, rules):
        seen.append(req["scenario"])
        return evaluate(rotation, req, env, rules)

    outcome = recommend(request, environment(), load_rules(BARAGAN), recording)
    assert outcome.diagnostics["scenario_status"] == "computed"
    assert {json.dumps(s, sort_keys=True) for s in seen} == {
        json.dumps({"temp_change_c": 2, "rain_change_pct": -20}, sort_keys=True),
        json.dumps({"temp_change_c": 0, "rain_change_pct": 0}, sort_keys=True),
    }
    reference = cached_run(make_request())
    warmer = cached_run(request)
    assert_valid(warmer)
    # P3's water scores fall with less rain and more heat, for the same sequence.
    shared = set(sequences(reference["plans"])) | set(sequences(warmer["plans"]))
    for seq in shared:
        assert p3(seq, request)["criteria"]["water"]["score"] < p3(seq, make_request())["criteria"]["water"]["score"]
    text = " ".join(t for p in warmer["plans"] for t in p["benefits"] + p["tradeoffs"] + [p["explanation"]])
    assert "current climate" in text and "baseline" not in text.lower()
    assert any("not a NASA forecast" in a for a in warmer["assumptions"])


# 5, 6. Current-rotation baseline --------------------------------------------------------


def test_current_rotation_produces_a_separate_p3_evaluated_baseline():
    request = make_request(current_rotation=["maize", "winter_wheat"])
    result = cached_run(request)
    assert_valid(result)
    baseline = result["baseline"]
    assert sequences([baseline]) == [("winter_wheat", "maize", "winter_wheat")]
    assert result["status"] == "complete" and len(result["plans"]) == 3
    criteria = p3(("winter_wheat", "maize", "winter_wheat"), request)["criteria"]
    assert baseline["scores"] == {n: criteria[n]["score"] for n in CRITERIA}
    assert baseline["violations"] == []
    assert any("current rotation" in t for p in result["plans"] for t in p["benefits"] + p["tradeoffs"])


def test_infeasible_current_rotation_keeps_p3_violations_and_explains_them():
    request = make_request(current_rotation=["sunflower"])
    result = cached_run(request)
    assert_valid(result)
    baseline = result["baseline"]
    expected = p3(("sunflower", "sunflower", "sunflower"), request)["violations"]
    assert expected and baseline["violations"] == expected
    assert baseline["tradeoffs"][0].startswith("Breaks a crop rotation rule")
    assert "not a recommendation" in baseline["explanation"]
    assert ("sunflower", "sunflower", "sunflower") not in sequences(result["plans"])


# 11. Exclusions and history ------------------------------------------------------------


def test_excluded_crops_never_appear_in_recommendations():
    request = make_request()
    request["constraints"]["excluded_crops"] = ["winter_wheat", "winter_barley"]
    result = cached_run(request)
    assert_valid(result)
    assert all(not {"winter_wheat", "winter_barley"} & set(s) for s in sequences(result["plans"]))


def test_history_constraints_from_p3_are_respected():
    request = make_request(history=[{"crop_id": "sunflower", "harvest_year": 2026, "source": "apia"}])
    result = cached_run(request)
    assert_valid(result)
    # P3's sunflower return interval (6 years) rules out sunflower in the next three crops.
    assert all("sunflower" not in s for s in sequences(result["plans"]))
    assert p3(("sunflower", "winter_wheat", "maize"), request)["feasibility"] == "infeasible"


# 13. Texts consistent with P3 evidence --------------------------------------------------


def test_local_checks_warnings_gaps_and_assumptions_carry_p3_evidence():
    request = make_request()
    result = cached_run(request)
    for plan in result["plans"]:
        evaluation = p3(sequences([plan])[0], request)
        for check in evaluation["local_checks"]:
            assert check in plan["local_checks"]
        for warning in evaluation["warnings"]:
            assert f"Watch out: {warning['message']}" in plan["tradeoffs"]
        for gap in evaluation["data_gaps"]:
            assert gap in result["data_gaps"]
        for assumption in evaluation["assumptions"]:
            assert assumption in result["assumptions"]
        # P3 marks soil and productivity as estimates: never "high" confidence.
        assert plan["confidence"] in ("low", "medium")
        assert "soil: estimate, not an observation" in plan["explanation"]


def test_texts_never_contradict_the_numbers_they_print():
    for request in (make_request(), make_request(scenario={"temp_change_c": 2, "rain_change_pct": -20})):
        for plan in cached_run(request)["plans"]:
            for line in plan["benefits"] + plan["tradeoffs"]:
                match = re.search(r"([\d.]+)/100, (below|as good as or better than) the typical option \(([\d.]+)/100\)", line)
                if match:
                    score, relation, median = float(match[1]), match[2], float(match[3])
                    assert (score < median) if relation == "below" else (score >= median), line


def test_user_facing_output_is_english():
    result = cached_run(make_request(current_rotation=["sunflower"], scenario={"temp_change_c": 1, "rain_change_pct": 0}))
    offenders = [t for t in user_texts(result) if romanian_hits(t)]
    assert not offenders


# 14. Unsupported region and missing environmental data ----------------------------------


def test_unsupported_region_returns_insufficient_data_with_p3_reason():
    result = cached_run(make_request(location=OUTSIDE))
    assert_valid(result)
    assert result["status"] == "insufficient_data" and result["plans"] == []
    assert any("outside the zones that have regional crop rules" in g for g in result["data_gaps"])
    assert not any("is not in the regional rules" in g for g in result["data_gaps"])


def test_unsupported_region_with_rotation_and_scenario_makes_no_false_scenario_claim():
    request = make_request(location=OUTSIDE, current_rotation=["maize", "winter_wheat"], scenario={"temp_change_c": 1, "rain_change_pct": 0})
    result = cached_run(request)
    assert_valid(result)
    assert "baseline" not in result and result["plans"] == []
    assert not any("did not confirm that the hypothetical scenario" in g for g in result["data_gaps"])


def test_crop_without_p3_rules_in_current_rotation_does_not_disable_the_scenario():
    request = make_request(current_rotation=["maize", "rice"], scenario={"temp_change_c": 1, "rain_change_pct": 0})
    outcome = recommend(request, environment(), load_rules(BARAGAN), evaluate)
    assert outcome.diagnostics["scenario_status"] == "computed"
    assert outcome.baseline is None
    assert any("could not establish its feasibility" in g for g in outcome.data_gaps)
    assert not any("did not confirm that the hypothetical scenario" in g for g in outcome.data_gaps)


def test_missing_daily_weather_gives_no_invented_plans():
    env = {k: v for k, v in json.loads(_raw_environment()).items() if k != "daily"}
    result = run(make_request(), env)
    assert_valid(result)
    assert result["status"] == "insufficient_data" and result["plans"] == []
    assert any("No daily weather" in g for g in result["data_gaps"])


# 15. Repeatability ---------------------------------------------------------------------


def test_identical_requests_give_identical_results_apart_from_timestamp():
    request = make_request(current_rotation=["maize", "winter_wheat"], scenario={"temp_change_c": 1, "rain_change_pct": -10})
    first = run(request)
    second = run(copy.deepcopy(request), json.loads(_raw_environment()))  # fresh environment object too
    for result in (first, second):
        result.pop("generated_at")
    assert first == second


# 16. Execution time versus ENGINE_TIMEOUT_MS --------------------------------------------


def engine_timeout_ms() -> int:
    for line in (ROOT / "apps" / "web" / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("ENGINE_TIMEOUT_MS="):
            return int(line.split("=", 1)[1])
    return 90000  # default in apps/web/src/lib/server/upstream.ts


def test_full_p3_p4_execution_time_is_well_within_engine_timeout(capsys):
    worst = make_request(
        priorities={"water": 3, "soil": 2, "climate": 2, "productivity": 3},
        current_rotation=["maize", "winter_wheat"],
        scenario={"temp_change_c": 1.5, "rain_change_pct": -15},
        constraints={"irrigated": True, "max_irrigation_mm": 250, "excluded_crops": []},
    )
    env = json.loads(_raw_environment())  # new object: P3 weather cache starts cold
    start = time.perf_counter()
    result = run(worst, env)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert_valid(result)
    timeout = engine_timeout_ms()
    with capsys.disabled():
        print(f"\n[P3+P4 timing] cold full request: {elapsed_ms:.0f} ms (ENGINE_TIMEOUT_MS={timeout})")
    assert elapsed_ms < 0.25 * timeout
