import pytest

from fieldshift import pipeline
from fieldshift.contracts import example, validate
from fieldshift.evaluator.rules import load_provisional_romania_rules
from fieldshift.geography import (
    UnsupportedLocationError,
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
    assert "ro-thermal-bands" in {source["id"] for source in rules["sources"]}
    assert rules["data_gaps"]


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
