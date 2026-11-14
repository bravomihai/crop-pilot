"""The optional contract fields (baseline, scores, local checks, history source,
productivity) validate, and the original examples stay valid without them."""

import copy

from fieldshift.contracts import example, validate


def test_full_examples_match_contracts():
    assert not validate("recommendation-request", example("recommendation-request.full"))
    assert not validate("recommendation-result", example("recommendation-result.full"))


def test_original_examples_need_none_of_the_optional_fields():
    request = example("recommendation-request")
    for key in ("current_rotation",):
        assert key not in request
    assert "productivity" not in request["priorities"]
    assert not validate("recommendation-request", request)
    assert not validate("recommendation-result", example("recommendation-result"))


def test_unknown_score_is_null_and_out_of_range_is_rejected():
    result = example("recommendation-result.full")
    assert result["plans"][0]["scores"]["productivity"] is None
    broken = copy.deepcopy(result)
    broken["plans"][0]["scores"]["water"] = 1.5
    assert validate("recommendation-result", broken)


def test_history_source_must_be_known():
    request = example("recommendation-request.full")
    request["history"][0]["source"] = "guess"
    assert validate("recommendation-request", request)
