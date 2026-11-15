import pytest

from fieldshift import pipeline
from fieldshift.contracts import example, validate
from fieldshift.evaluator.rules import load_provisional_romania_rules
from fieldshift.geography import (
    UnsupportedLocationError,
    field_sample_points,
    validate_field_boundary,
    validate_location,
)
from fieldshift.recommender.engine import recommend
from fieldshift.recommender.generation import CandidateSet


def test_provisional_romania_rules_shift_cool_zone_calendar():
    environment = {
        "daily": [
            {"date": "2020-04-15", "values": {"T2M": 14.0}},
            {"date": "2020-09-15", "values": {"T2M": 14.0}},
        ]
    }

    rules = load_provisional_romania_rules(
        {"latitude": 46.77, "longitude": 23.59}, environment
    )

    pea = next(crop for crop in rules["crops"] if crop["id"] == "pea")
    assert rules["region"]["id"] == "ro-romania-provisional-cool"
    assert pea["sowing"]["start"] == "04-01"
    assert pea["harvest"]["start"] == "07-15"
    assert {
        "oats", "sorghum", "dry_beans", "sugar_beet",
        "spring_barley", "triticale", "winter_rye", "potato",
    } <= {
        crop["id"] for crop in rules["crops"]
    }
    assert "ro-thermal-bands" in {source["id"] for source in rules["sources"]}
    assert any("provisional" in gap and "agronomist" in gap for gap in rules["data_gaps"])


def test_romania_location_and_field_boundary_validation():
    validate_location({"latitude": 46.77, "longitude": 23.59})
    with pytest.raises(UnsupportedLocationError):
        validate_location({"latitude": 47.5, "longitude": 19.0})

    boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [26.4, 44.4],
                [26.5, 44.4],
                [26.5, 44.5],
                [26.4, 44.5],
                [26.4, 44.4],
            ]
        ],
    }
    validate_field_boundary(boundary, {"latitude": 44.45, "longitude": 26.45})
    with pytest.raises(UnsupportedLocationError):
        validate_field_boundary(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [18.9, 45.5],
                        [19.0, 45.5],
                        [19.0, 45.6],
                        [18.9, 45.6],
                        [18.9, 45.5],
                    ]
                ],
            }
        )


def test_field_sample_points_are_deterministic_and_inside_the_boundary():
    boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [26.4, 44.4],
                [26.5, 44.4],
                [26.5, 44.5],
                [26.4, 44.5],
                [26.4, 44.4],
            ]
        ],
    }
    location = {"latitude": 44.45, "longitude": 26.45}

    samples = field_sample_points(boundary, location)

    assert len(samples) == 3
    assert samples[0] == location
    assert samples == field_sample_points(boundary, location)
    for sample in samples:
        validate_field_boundary(boundary, sample)


def test_computed_result_keeps_monthly_climate_and_field_data_gap(monkeypatch):
    request = example("recommendation-request")
    request["field_boundary"] = {
        "type": "Polygon",
        "coordinates": [
            [
                [26.4, 44.4],
                [26.5, 44.4],
                [26.5, 44.5],
                [26.4, 44.5],
                [26.4, 44.4],
            ]
        ],
    }
    monkeypatch.setattr(pipeline, "recommend_rotations", lambda *args: [])
    monthly_climate = [
        {
            "month": "2024-07",
            "mean_daily_max_c": 30.0,
            "max_daily_max_c": 37.0,
            "mean_daily_min_c": 18.0,
            "min_daily_min_c": 12.0,
            "max_temp_observations": 31,
            "min_temp_observations": 31,
        }
    ]

    result = pipeline.computed_result(
        request,
        "computed-test",
        {
            "monthly_climate": monthly_climate,
            "sources": [{"id": "nasa-power", "title": "NASA POWER"}],
            "data_gaps": ["Soil data unavailable."],
            "assumptions": [],
        },
        {"sources": [], "data_gaps": ["Provisional regional rules."]},
        lambda *args: {},
    )

    assert validate("recommendation-result", result) == []
    assert result["monthly_climate"] == monthly_climate
    assert "quality" not in result
    assert "Soil data unavailable." in result["data_gaps"]
    assert "Provisional regional rules." in result["data_gaps"]
    assert any("representative point" in gap for gap in result["data_gaps"])


def test_incompatible_land_cover_returns_no_plans_without_fetching_weather(monkeypatch):
    request = example("recommendation-request")
    monkeypatch.setenv("ENGINE_MODE", "computed")
    monkeypatch.setattr(
        pipeline, "assess_land_cover",
        lambda boundary: ({"status": "incompatible", "message": "Tree cover in 2021."},
                          [{"id": "worldcover", "title": "WorldCover 2021"}]),
    )

    def unexpected(request):
        pytest.fail("Weather and plans should not be fetched for incompatible land")

    monkeypatch.setattr(pipeline, "build_environment", unexpected)
    result = pipeline.recommend(request, "forest-test")
    assert result["status"] == "insufficient_data"
    assert result["plans"] == []
    assert result["request_id"] == "forest-test"
    assert result["land_cover"]["status"] == "incompatible"
    assert validate("recommendation-result", result) == []


def test_uncertain_land_cover_keeps_plans_and_warning(monkeypatch):
    request = example("recommendation-request")
    monkeypatch.setenv("ENGINE_MODE", "computed")
    monkeypatch.setattr(
        pipeline, "assess_land_cover",
        lambda boundary: ({"status": "uncertain", "message": "Verify the field."}, []),
    )
    monkeypatch.setattr(pipeline, "build_environment", lambda request: {"sources": []})
    monkeypatch.setattr(pipeline, "load_rules", lambda location: {"crops": ["crop"]})
    monkeypatch.setattr(
        pipeline, "computed_result",
        lambda *args: {"plans": ["existing plan"], "assumptions": []},
    )
    result = pipeline.recommend(request, "uncertain-test")
    assert result["plans"] == ["existing plan"]
    assert result["land_cover"]["status"] == "uncertain"


def test_selected_crop_shortlist_filters_new_candidates(monkeypatch):
    request = example("recommendation-request")
    request["constraints"]["selected_crops"] = ["pea", "maize"]
    request["constraints"]["selected_crops_only"] = True
    rules = {
        "crops": [
            {"id": "pea", "name": "Pea"},
            {"id": "maize", "name": "Maize"},
            {"id": "winter_wheat", "name": "Winter wheat"},
        ]
    }
    seen = {}

    def candidates(catalog, excluded, max_candidates):
        seen.update(catalog)
        return CandidateSet((), tuple(sorted(catalog)), 0, False)

    monkeypatch.setattr(
        "fieldshift.recommender.engine.generate_candidates", candidates
    )
    recommend(request, {}, rules, lambda *args: {})

    assert set(seen) == {"pea", "maize"}
