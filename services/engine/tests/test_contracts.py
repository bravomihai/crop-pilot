from datetime import date
from fieldshift.contracts import example, validate
from fieldshift.demo import CATALOG, recommend_demo, demo_steps


def test_fixtures_match_contracts():
    for name in ["recommendation-request", "recommendation-result"]:
        assert not validate(name, example(name))


def test_three_steps_are_temporal_not_calendar_years():
    steps = demo_steps(("pea", "winter_wheat", "maize"), date(2027, 3, 1))
    assert steps[0]["harvest_window"]["end"] < steps[1]["sowing_window"]["start"]
    assert (
        steps[1]["sowing_window"]["start"][:4] == steps[0]["sowing_window"]["start"][:4]
    )
    assert steps[1]["harvest_window"]["start"][:4] == "2028"


def test_exclusions_do_not_force_three_invalid_alternatives():
    request = example("recommendation-request")
    request["constraints"]["excluded_crops"] = list(CATALOG)
    output = recommend_demo(request, "test")
    assert output["status"] == "insufficient_data" and output["plans"] == []


def test_every_demo_response_is_marked_as_fictional():
    output = recommend_demo(example("recommendation-request"), "test")
    assert output["mode"] == "demo"
    assert all(p["confidence"] == "low" for p in output["plans"])
    assert output["sources"][0]["id"] == "demo-fixture"


def test_selected_new_romanian_crops_are_available_in_demo_mode():
    request = example("recommendation-request")
    request["constraints"]["selected_crops"] = ["spring_barley", "potato", "winter_rye"]
    request["constraints"]["selected_crops_only"] = True
    output = recommend_demo(request, "test")
    assert output["plans"]
    assert {step["crop_id"] for step in output["plans"][0]["steps"]} == {
        "spring_barley",
        "potato",
        "winter_rye",
    }
