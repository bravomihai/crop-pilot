"""Regression tests for the whole-application audit (2026-11-14).

Real P3/P4 on the historical NASA POWER fixture, with P2's real `build_environment`
run offline (network calls replaced). No fake evaluator.
"""

from __future__ import annotations

import os
import re
import time
from datetime import date
from unittest import mock

import pytest

from fieldshift import data_service, pipeline
from test_p4_web_integration import cached_run, dashboard_request, environment, p2_built_environment, run

EXCLUDED_FOR_LIMITED = ["winter_wheat", "winter_barley", "sunflower", "soybean", "pea"]


def test_missing_data_lists_each_winterkill_note_once_per_crop():
    result = run(dashboard_request(), p2_built_environment(dashboard_request()))
    notes = [g for g in result["data_gaps"] if g.startswith("Winterkill risk")]
    assert notes, "the fixture's plans include winter crops"
    assert all(re.fullmatch(r"Winterkill risk for [a-z ]+ ignores snow cover.*", g) and "," not in g.split(" ignores")[0] for g in notes), notes
    assert len(notes) == len(set(notes)) <= 3
    assert len(result["data_gaps"]) < 15, result["data_gaps"]


def test_past_availability_date_starts_from_today(monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "computed")
    monkeypatch.setattr(pipeline, "build_environment", p2_built_environment)
    result = pipeline.recommend(dashboard_request(available_from="2020-03-01"), "past")
    today = date.today().isoformat()
    assert result["assumptions"][0].startswith("The field availability date (2020-03-01) is in the past")
    for plan in result["plans"]:
        assert plan["steps"][0]["sowing_window"]["start"] >= today


def test_future_availability_date_is_unchanged():
    request = dashboard_request(available_from="2031-06-15")
    assert pipeline.start_from_today(request) == (request, None)


def test_inputs_without_effect_are_reported():
    result = cached_run(dashboard_request(constraints={
        "irrigated": False, "max_irrigation_mm": 300, "excluded_crops": ["pea"],
        "selected_crops": ["pea", "maize", "winter_wheat", "rice"], "selected_crops_only": True,
    }))
    text = " ".join(result["assumptions"])
    assert "irrigation is off; the plans are rain-fed" in text
    assert "Shortlisted crop(s) without regional rules were skipped: Rice." in text
    assert "Crop(s) both shortlisted and excluded were excluded: Pea." in text
    not_applied = cached_run(dashboard_request(constraints={"irrigated": False, "excluded_crops": [], "selected_crops": ["pea"]}))
    assert any("shortlist was given but not applied" in a for a in not_applied["assumptions"])


def test_high_elevation_is_disclosed():
    env = environment()
    env["static"] = {**env["static"], "elevation_m": 1250}
    result = run(dashboard_request(), env)
    assert any("about 1250 m" in g for g in result["data_gaps"])
    assert not any("elevation is about" in g for g in cached_run(dashboard_request())["data_gaps"])


def test_current_rotation_violations_are_agronomic_rules_only():
    result = cached_run(dashboard_request(constraints={"irrigated": False, "excluded_crops": EXCLUDED_FOR_LIMITED}))
    baseline = result["baseline"]
    assert not any("excluded" in v for v in baseline["violations"]), baseline["violations"]
    assert "Includes crop(s) you excluded from the recommendations: Winter wheat." in baseline["tradeoffs"]


def _slow(seconds, value):
    def fetch(*args):
        time.sleep(seconds)
        return value
    return fetch


def test_p2_providers_run_in_parallel_and_late_soil_becomes_a_gap(monkeypatch):
    monkeypatch.setenv("DATA_DEADLINE_S", "1.0")
    env_power = {
        "location": {"latitude": 44.56, "longitude": 27.36}, "period": environment()["period"],
        "elevation_m": 32.0, "daily": environment()["daily"][:400], "parameters": {},
        "sources": [{"id": "nasa-power", "title": "NASA POWER Daily API"}], "retrieved_at": "x", "data_gaps": [],
    }
    with (
        mock.patch.object(data_service, "fetch_power", _slow(0.4, env_power)),
        mock.patch.object(data_service, "fetch_soil", _slow(3.0, (None, [], []))),
        mock.patch.object(data_service, "fetch_slope", _slow(0.4, (None, [], ["no slope"]))),
        mock.patch.dict(os.environ, {"ENABLE_NASA_POWER": "true"}),
    ):
        started = time.monotonic()
        env = data_service.build_environment(dashboard_request())
        elapsed = time.monotonic() - started
    assert elapsed < 1.6, f"parallel fetch with a 1 s deadline took {elapsed:.1f} s"
    assert "SoilGrids did not respond in time; soil properties are unknown." in env["data_gaps"]
    assert "no slope" in env["data_gaps"]


def test_p2_late_nasa_power_fails_the_request(monkeypatch):
    monkeypatch.setenv("DATA_DEADLINE_S", "0.3")
    with (
        mock.patch.object(data_service, "fetch_power", _slow(2.0, {})),
        mock.patch.object(data_service, "fetch_soil", _slow(0, (None, [], []))),
        mock.patch.object(data_service, "fetch_slope", _slow(0, (None, [], []))),
        mock.patch.dict(os.environ, {"ENABLE_NASA_POWER": "true"}),
    ):
        with pytest.raises(TimeoutError, match="NASA POWER"):
            data_service.build_environment(dashboard_request())
