"""Every component's output must match its contract. Run: pytest (from engine/)."""

import pytest

from fieldshift.contracts import example, validate
from fieldshift.data import fetch_field_data
from fieldshift.evaluator import evaluate, load_rules
from fieldshift.pipeline import analyze


@pytest.mark.parametrize("name", ["farm-request", "field-data", "crop-rules", "evaluation", "analysis-result"])
def test_examples_are_valid(name):
    assert validate(name, example(name)) == []


def test_field_data_contract():
    assert validate("field-data", fetch_field_data(44.2, 27.33, 2015, 2024)) == []


def test_rules_contract():
    assert validate("crop-rules", load_rules()) == []


def test_evaluation_contract():
    farm = example("farm-request")
    fd = example("field-data")
    out = evaluate(["soybean", "winter_wheat", "maize"], farm, fd, load_rules())
    assert validate("evaluation", out) == []


def test_pipeline_contract():
    farm = example("farm-request")
    farm["farm_id"] = "farm_test"
    result = analyze(farm)
    assert validate("analysis-result", result) == []
    assert result["strategies"][0]["kind"] == "existing"
    assert result["strategies"][0]["sequence"] == farm["current_rotation"]
    assert abs(sum(result["weights_used"].values()) - 1) < 0.01
