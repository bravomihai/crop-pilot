"""Contract fields `plan.replay` and `result.climate_context`, end to end on real NASA POWER data."""

import copy
import json
from pathlib import Path

import pytest

from fieldshift.contracts import example, validate
from fieldshift.evaluator import climate_context, evaluate, load_rules
from fieldshift.pipeline import computed_result
from fieldshift.recommender.evaluation import parse_evaluation
from fieldshift.recommender.validation import validate_result_semantics

FIXTURE = Path(__file__).parent / "fixtures" / "environment-ro-south.json"


@pytest.fixture(scope="module")
def environment():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def result(environment):
    request = example("recommendation-request.full")
    return computed_result(request, "replay-test", environment, load_rules(request["location"]), evaluate)


def test_result_with_replay_and_climate_matches_the_contract(result):
    assert validate("recommendation-result", result) == []
    assert validate_result_semantics(result) == []
    assert "climate_context" in result and result["baseline"]["replay"]


def test_every_plan_carries_its_replay_oldest_first(result):
    for plan in result["plans"] + [result["baseline"]]:
        replay = plan["replay"]
        years = [season["season_start_year"] for season in replay]
        assert len(replay) >= 15 and years == sorted(years) and len(set(years)) == len(years)
        crops = [step["crop_id"] for step in plan["steps"]]
        for season in replay:
            assert [step["crop_id"] for step in season["steps"]] == crops
            assert all(0 <= v <= 1 for v in season["scores"].values() if v is not None)


def test_replay_reflects_the_scenario(environment):
    request = example("recommendation-request.full")
    rules = load_rules(request["location"])
    rotation = ["winter_wheat", "maize", "soybean"]
    request["scenario"] = {"temp_change_c": 0, "rain_change_pct": 0}
    base = evaluate(rotation, request, environment, rules)["replay"]
    request["scenario"] = {"temp_change_c": 2, "rain_change_pct": -20}
    hot = evaluate(rotation, request, environment, rules)["replay"]
    assert sum(s["scores"]["water"] for s in hot) < sum(s["scores"]["water"] for s in base)


def test_climate_context_is_observed_complete_years(environment):
    climate = climate_context(environment, {"latitude": 44.56, "longitude": 27.36})
    assert climate["basis"] == "observed"
    assert climate["period"] == {"start_year": 2005, "end_year": 2025}
    assert [y["year"] for y in climate["years"]] == list(range(2005, 2026))
    year_2024 = next(y for y in climate["years"] if y["year"] == 2024)
    assert year_2024["hot_days_gt32"] > 60 and year_2024["rain_mm"] > 0
    assert {"rain_mm", "hot_days_gt32", "tmean_c", "et0_mm"} <= set(climate["trends"])
    assert climate["source_ids"] == ["nasa-power"]


def test_climate_context_needs_daily_data():
    assert climate_context({"sources": []}, {"latitude": 44.5, "longitude": 27.3}) is None


def test_malformed_replay_is_dropped_not_repaired():
    raw = {
        "feasibility": "unknown",
        "replay": [
            {"season_start_year": 2012, "scores": {"water": 0.5}},
            {"season_start_year": 2010, "scores": {"water": 1.7}},  # out of range
            {"season_start_year": 2011, "scores": {"water": 0.6}, "steps": [{"crop_id": "maize"}]},  # wrong crop
            {"season_start_year": 2009, "scores": {"water": None}},
        ],
    }
    evaluation = parse_evaluation(raw, ("pea", "winter_wheat", "sunflower"))
    assert [s["season_start_year"] for s in evaluation.replay] == [2009, 2012]
    assert sum("replay season dropped" in e for e in evaluation.contract_errors) == 2


def test_semantic_checks_catch_unordered_replay_and_unknown_climate_source(result):
    broken = copy.deepcopy(result)
    broken["plans"][0]["replay"].reverse()
    broken["climate_context"]["source_ids"] = ["not-listed"]
    errors = validate_result_semantics(broken)
    assert "Replay seasons must be in increasing year order." in errors
    assert "Unknown source reference in climate context." in errors


def test_outside_zone_message_reaches_the_result(environment):
    request = example("recommendation-request")
    request["location"] = {"latitude": 46.77, "longitude": 23.6}
    out = computed_result(request, "cluj", environment, load_rules(request["location"]), evaluate)
    assert out["status"] == "insufficient_data"
    assert any("outside the zones" in gap for gap in out["data_gaps"])


def test_replay_seasons_carry_the_historical_start_date_for_fair_comparison(result):
    """Survival Mode compares plans on the same past season: `field_free_from` lines them up.

    Plans may sow their first crop in different years (autumn wheat vs spring maize), so
    `season_start_year` alone would pair different historical windows.
    """
    request = example("recommendation-request.full")
    free = request["available_from"]
    plans = result["plans"] + [result["baseline"]]
    for plan in plans:
        for season in plan["replay"]:
            start = season["field_free_from"]
            assert start[4:] == free[4:]  # same month and day, moved back whole years
            first_sowing_year = int(plan["steps"][0]["sowing_window"]["start"][:4])
            shift = int(free[:4]) - int(start[:4])
            assert season["season_start_year"] == first_sowing_year - shift
    # Every plan's replay starts from dates drawn from the same set of past years.
    shared = set.intersection(*({s["field_free_from"] for s in p["replay"]} for p in plans))
    assert len(shared) >= 10


def test_replay_start_date_is_checked_and_passed_through():
    raw = {
        "feasibility": "unknown",
        "replay": [
            {"season_start_year": 2012, "field_free_from": "2011-10-01", "scores": {"water": 0.5}},
            {"season_start_year": 2013, "field_free_from": "not-a-date", "scores": {"water": 0.5}},
            {"season_start_year": 2014, "scores": {"water": 0.4}},
        ],
    }
    evaluation = parse_evaluation(raw, ("winter_wheat", "maize", "soybean"))
    assert [s.get("field_free_from") for s in evaluation.replay] == ["2011-10-01", None]
    assert sum("replay season dropped" in e for e in evaluation.contract_errors) == 1
