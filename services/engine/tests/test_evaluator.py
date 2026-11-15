"""P3 evaluator: rules, calendar, replay over real NASA POWER seasons, output shape.

The fixture is real NASA POWER daily data (2005–2025) for a test point in the Bărăgan.
These tests check the evaluator's logic and contract; they are not agronomic validation.
"""

import copy
import itertools
import json
import time
from datetime import date
from pathlib import Path

import pytest

from fieldshift.contracts import example
from fieldshift.evaluator import evaluate, load_rules
from fieldshift.recommender.crop_assessment import assess_crops

FIXTURE = Path(__file__).parent / "fixtures" / "environment-ro-south.json"
CRITERIA = ("water", "soil", "climate", "productivity")


@pytest.fixture(scope="module")
def environment():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def request_():
    request = example("recommendation-request.full")
    request["scenario"] = {"temp_change_c": 0, "rain_change_pct": 0}
    return request


@pytest.fixture(scope="module")
def rules():
    return load_rules({"latitude": 44.56, "longitude": 27.36})


def test_rules_cover_the_southern_plains_only():
    inside = load_rules({"latitude": 44.45, "longitude": 26.5})
    assert {c["id"] for c in inside["crops"]} >= {
        "winter_wheat", "winter_barley", "winter_rapeseed", "maize", "sunflower",
        "soybean", "pea", "oats", "sorghum", "dry_beans", "sugar_beet",
        "spring_barley", "triticale", "winter_rye", "potato",
    }
    assert all(c["name"] for c in inside["crops"])
    outside = load_rules({"latitude": 46.77, "longitude": 23.6})  # Cluj, Transylvania
    assert outside["crops"] == [] and "outside" in outside["data_gaps"][0]


def test_crop_display_names_are_english_and_do_not_keep_unused_localized_aliases(rules):
    active_rules = rules
    assert all("name_ro" not in crop for crop in active_rules["crops"])
    assert {crop["id"]: crop["name"] for crop in active_rules["crops"]}["winter_wheat"] == "Winter wheat"

    profile = json.loads(
        (Path(__file__).parents[1] / "fieldshift" / "crop_rules.json").read_text(
            encoding="utf-8"
        )
    )
    assert {crop["name"] for crop in profile["crops"]} == {
        "Pea",
        "Maize",
        "Winter wheat",
        "Winter barley",
        "Sunflower",
    }
    assert {
        band["name"] for band in profile["region"]["thermal_bands"].values()
    } == {"warm", "temperate", "cool"}


def test_new_crop_rules_and_successor_matrix_are_complete(rules):
    crops = {crop["id"]: crop for crop in rules["crops"]}
    new_ids = {
        "oats", "sorghum", "dry_beans", "sugar_beet",
        "spring_barley", "triticale", "winter_rye", "potato",
    }
    assert new_ids <= crops.keys()
    assert all(crops[crop_id]["family"] and crops[crop_id]["ecocrop"] for crop_id in new_ids)
    assert crops["dry_beans"]["legume"] is True
    assert crops["sugar_beet"]["legume"] is False
    expected_successors = set(crops)
    assert set(rules["successor"]) == expected_successors
    assert all(set(row) == expected_successors for row in rules["successor"].values())
    assert any("provisional" in gap and "agronomist" in gap for gap in rules["data_gaps"])


@pytest.mark.parametrize(
    "rotation",
    [
        ["oats", "dry_beans", "sorghum"],
        ["sugar_beet", "oats", "dry_beans"],
        ["potato", "spring_barley", "dry_beans"],
        ["triticale", "potato", "winter_rye"],
    ],
)
def test_new_crop_rotations_are_evaluable(rotation, request_, environment, rules):
    out = evaluate(rotation, request_, environment, rules)
    assert out["feasibility"] == "feasible"
    assert [step["crop_id"] for step in out["calendar"]] == rotation
    assert out["criteria"]["water"]["score"] is not None


def test_every_cited_source_is_listed(rules):
    ids = {s["id"] for s in rules["sources"]}
    assert {"fao56", "fao-wrsi", "ecocrop", "ro-agronomy", "crop-temperature-thresholds"} <= ids
    assert all(s.get("title") for s in rules["sources"])


def test_output_shape_matches_what_the_recommender_reads(request_, environment, rules):
    out = evaluate(["pea", "winter_wheat", "maize"], request_, environment, rules)
    assert out["feasibility"] == "feasible" and out["violations"] == []
    assert set(out["criteria"]) == set(CRITERIA)
    for name in CRITERIA:
        criterion = out["criteria"][name]
        assert 0 <= criterion["score"] <= 1
        assert criterion["basis"] in ("observed", "derived", "estimated", "assumed")
        assert criterion["summary"]
    listed = {s["id"] for s in out["sources"]}
    cited = set(out["source_ids"]) | {i for c in out["criteria"].values() for i in c["source_ids"]}
    cited |= {i for step in out["calendar"] for i in step["source_ids"]}
    assert cited <= listed
    assert all(s.get("title") for s in out["sources"])
    assert out["fixture"] is False and out["scenario_applied"] is False
    assert len(out["details"]) == 3 and len(out["replay"]) >= 15
    assert out["local_checks"]

def test_individual_crop_assessment_uses_real_evaluator(request_, environment, rules):
    request_["assessment_crops"] = ["potato"]
    result = assess_crops(request_, environment, rules, evaluate)
    assert result["selected"][0]["crop_id"] == "potato"
    assert result["selected"][0]["score"] is not None
    assert result["selected"][0]["sowing_window"]["start"] >= request_["available_from"]
    assert result["selected"][0]["harvest_window"]["start"] > result["selected"][0]["sowing_window"]["end"]
    assert result["alternatives"]
    assert all(crop["crop_id"] != "potato" for crop in result["alternatives"])


def test_calendar_is_ordered_and_does_not_overlap(request_, environment, rules):
    for rotation in (["winter_wheat", "maize", "winter_wheat"], ["pea", "winter_rapeseed", "sunflower"]):
        steps = evaluate(rotation, request_, environment, rules)["calendar"]
        assert [s["crop_id"] for s in steps] == rotation
        assert steps[0]["sowing_window"]["end"] >= request_["available_from"]
        for step in steps:
            assert step["sowing_window"]["start"] <= step["sowing_window"]["end"] <= step["harvest_window"]["start"]
            assert step["harvest_window"]["start"] <= step["harvest_window"]["end"]
        for a, b in zip(steps, steps[1:]):
            assert a["harvest_window"]["end"] < b["sowing_window"]["start"]


def test_autumn_crop_crosses_the_year(request_, environment, rules):
    request_["available_from"] = "2027-03-01"
    steps = evaluate(["pea", "winter_wheat", "maize"], request_, environment, rules)["calendar"]
    assert steps[1]["sowing_window"]["start"].startswith("2027-10")
    assert steps[1]["harvest_window"]["start"].startswith("2028-06")
    assert steps[2]["sowing_window"]["start"].startswith("2029-04")


def test_wheat_right_after_maize_is_sown_late(request_, environment, rules):
    out = evaluate(["winter_wheat", "maize", "winter_wheat"], request_, environment, rules)
    messages = " ".join(w["message"] for w in out["warnings"])
    assert "after its optimal window" in messages and "Tight turnaround" in messages


@pytest.mark.parametrize(
    "rotation, words",
    [
        (["winter_rapeseed", "sunflower", "winter_wheat"], "white mould"),
        (["sunflower", "winter_wheat", "sunflower"], "minimum interval is 6"),
        (["pea", "pea", "winter_wheat"], "Pea after pea"),
        (["maize", "maize", "maize"], "3 times in a row"),
    ],
)
def test_rotation_rules_make_sequences_infeasible(rotation, words, request_, environment, rules):
    request_["history"] = []
    out = evaluate(rotation, request_, environment, rules)
    assert out["feasibility"] == "infeasible"
    assert any(words in v for v in out["violations"]), out["violations"]


def test_history_counts_for_the_first_crop_and_return_intervals(request_, environment, rules):
    request_["history"] = [{"crop_id": "sunflower", "harvest_year": 2026, "source": "typed"}]
    after_sunflower = evaluate(["soybean", "winter_wheat", "maize"], request_, environment, rules)
    assert after_sunflower["feasibility"] == "infeasible"
    request_["history"] = [{"crop_id": "sunflower", "harvest_year": 2024}, {"crop_id": "maize", "harvest_year": 2026}]
    too_soon = evaluate(["winter_wheat", "sunflower", "winter_barley"], request_, environment, rules)
    assert any("minimum interval is 6" in v for v in too_soon["violations"])


def test_excluded_crop_is_a_violation(request_, environment, rules):
    request_["constraints"]["excluded_crops"] = ["maize"]
    out = evaluate(["pea", "winter_wheat", "maize"], request_, environment, rules)
    assert out["feasibility"] == "infeasible"


def test_hot_dry_scenario_lowers_water_and_is_reported(request_, environment, rules):
    base = evaluate(["winter_wheat", "maize", "soybean"], request_, environment, rules)
    hot = copy.deepcopy(request_)
    hot["scenario"] = {"temp_change_c": 2, "rain_change_pct": -20}
    out = evaluate(["winter_wheat", "maize", "soybean"], hot, environment, rules)
    assert out["scenario_applied"] is True
    assert out["criteria"]["water"]["score"] < base["criteria"]["water"]["score"]
    assert out["criteria"]["productivity"]["score"] < base["criteria"]["productivity"]["score"]


def test_legume_rotation_scores_better_on_soil_than_cereal_monotony(request_, environment, rules):
    request_["history"] = []
    legume = evaluate(["pea", "winter_wheat", "sunflower"], request_, environment, rules)
    cereals = evaluate(["winter_wheat", "maize", "winter_barley"], request_, environment, rules)
    assert legume["criteria"]["soil"]["score"] > cereals["criteria"]["soil"]["score"]


def test_irrigation_raises_productivity_not_water(request_, environment, rules):
    rainfed = evaluate(["maize", "winter_wheat", "soybean"], request_, environment, rules)
    request_["constraints"]["irrigated"] = True
    watered = evaluate(["maize", "winter_wheat", "soybean"], request_, environment, rules)
    assert watered["criteria"]["productivity"]["score"] > rainfed["criteria"]["productivity"]["score"]
    assert watered["criteria"]["water"]["score"] == rainfed["criteria"]["water"]["score"]
    assert all("irrigation_mm_mean" in d for d in watered["details"])


def test_without_weather_scores_are_unknown_not_neutral(request_, rules):
    out = evaluate(["pea", "winter_wheat", "maize"], request_, {"sources": []}, rules)
    assert out["feasibility"] == "feasible"
    assert out["criteria"]["soil"]["score"] is not None
    for name in ("water", "climate", "productivity"):
        assert out["criteria"][name]["score"] is None
    assert any("No daily weather" in g for g in out["data_gaps"])


def test_unknown_crop_or_region_is_unknown(request_, environment, rules):
    assert evaluate(["pea", "rice", "maize"], request_, environment, rules)["feasibility"] == "unknown"
    outside = load_rules({"latitude": 46.77, "longitude": 23.6})
    assert evaluate(["pea", "winter_wheat", "maize"], request_, environment, outside)["feasibility"] == "unknown"


def test_whole_search_space_is_fast(request_, environment, rules):
    crops = [c["id"] for c in rules["crops"]]
    start = time.perf_counter()
    results = [evaluate(list(r), request_, environment, rules) for r in itertools.product(crops, repeat=3)]
    elapsed = time.perf_counter() - start
    assert len(results) == len(crops) ** 3
    assert sum(r["feasibility"] == "feasible" for r in results) > 20
    assert elapsed < 30


def test_cache_never_serves_another_environments_weather(request_, environment, rules):
    # Two environments with the same shape and point but different weather, built one
    # after the other, as two requests would be. The second must not reuse the first.
    rotation = ["pea", "winter_wheat", "maize"]
    first = evaluate(rotation, request_, copy.deepcopy(environment), rules)
    drier = copy.deepcopy(environment)
    for day in drier["daily"]:
        if day["values"].get("PRECTOTCORR") is not None:
            day["values"]["PRECTOTCORR"] *= 0.5
    second = evaluate(rotation, request_, drier, rules)
    assert second["criteria"]["water"]["score"] < first["criteria"]["water"]["score"]


def test_repeated_evaluation_is_stable(request_, environment, rules):
    rotation = ["winter_rapeseed", "winter_wheat", "sunflower"]
    a = evaluate(rotation, request_, environment, rules)
    b = evaluate(rotation, request_, environment, rules)
    assert a["criteria"] == b["criteria"] and a["replay"] == b["replay"]


def test_winterkill_note_only_for_winter_crops(request_, environment, rules):
    spring = evaluate(["maize", "sunflower", "soybean"], request_, environment, rules)
    winter = evaluate(["pea", "winter_wheat", "maize"], request_, environment, rules)
    assert not any("Winterkill" in g for g in spring["data_gaps"])
    assert any("Winterkill risk for winter wheat" in g for g in winter["data_gaps"])


def test_provisional_profile_reads_the_data_services_cleaned_days():
    # build_environment returns flat cleaned days (tmean, tmin, tmax), not raw POWER values.
    from fieldshift.evaluator.rules import load_provisional_romania_rules

    cluj = {"latitude": 46.73, "longitude": 23.75}
    cleaned = {"daily": [{"date": f"2020-{m:02d}-15", "tmean": 16.0, "tmin": 9.0, "tmax": 23.0} for m in range(4, 10)]}
    only_min_max = {"daily": [{"date": f"2020-{m:02d}-15", "tmean": None, "tmin": 9.0, "tmax": 23.0} for m in range(4, 10)]}
    for environment in (cleaned, only_min_max):
        rules = load_provisional_romania_rules(cluj, environment)
        assert rules["crops"], rules.get("data_gaps")
        assert rules["region"]["id"].startswith("ro-romania-provisional-")
        assert rules["region"]["mean_apr_sep_t2m_c"] == 16.0


def test_fusarium_check_only_when_wheat_follows_maize(request_, environment, rules):
    request_["history"] = [{"crop_id": "sunflower", "harvest_year": 2026}]
    no_maize = evaluate(["pea", "winter_wheat", "winter_rapeseed"], request_, environment, rules)
    after_maize = evaluate(["maize", "winter_wheat", "pea"], request_, environment, rules)
    assert not any("Fusarium" in c for c in no_maize["local_checks"])
    assert any("Fusarium" in c for c in after_maize["local_checks"])


def test_maize_rootworm_check_only_for_maize_after_maize(request_, environment, rules):
    request_["history"] = [{"crop_id": "maize", "harvest_year": 2026}]
    repeat = evaluate(["maize", "winter_wheat", "pea"], request_, environment, rules)
    request_["history"] = [{"crop_id": "winter_wheat", "harvest_year": 2026}]
    first = evaluate(["maize", "winter_wheat", "pea"], request_, environment, rules)
    assert any("Diabrotica" in c for c in repeat["local_checks"])
    assert not any("Diabrotica" in c for c in first["local_checks"])


@pytest.mark.parametrize("rotation", [
    ["sunflower", "winter_barley", "winter_barley"],
    ["pea", "winter_wheat", "winter_wheat"],
])
def test_straw_cereal_after_itself_is_not_recommended(rotation, request_, environment, rules):
    request_["history"] = []
    out = evaluate(rotation, request_, environment, rules)
    assert out["feasibility"] == "infeasible", out["violations"]
