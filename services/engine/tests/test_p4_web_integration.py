"""Full-stack boundary checks for REAL P3–P4 computed results (no fake evaluator).

Environment: the historical NASA POWER fixture (tests/fixtures/environment-ro-south.json),
standing in for P2. Requests use the exact shapes the merged frontend builds
(apps/web/src/components/field-dashboard.tsx and calculator.tsx).

What this file verifies, in Python only:
- the internal FastAPI endpoint returns real computed results over in-process HTTP
  (FastAPI TestClient; P2's real `build_environment` with only its network calls replaced
  by the fixture: no server, no network);
- the result satisfies the checks the Next.js route applies before forwarding it
  (`apps/web/src/lib/server/engine.ts`), mirrored here as `next_route_errors`;
- user-facing text regressions found in the full-stack audit (raw crop IDs, doubled
  punctuation, equal-looking numbers in comparisons, lists repeated in the explanation);
- P2's real `build_environment` output (network calls replaced offline) is accepted by
  P3–P4 and gives the same scores as the fixture.

What it does NOT verify: the Next.js handler itself, Zod parsing in Node, React rendering
or the browser flow. Those were checked with the Node harness described in
docs/P4_IMPLEMENTATION_REPORT.md ("Full-stack integration audit"), which needs the
installed web dependencies; a browser flow needs running servers. Passing these tests is
not agronomic validation.
"""

from __future__ import annotations

import copy
import json
import os
import re
from functools import lru_cache
from unittest import mock
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldshift import data_service, pipeline
from fieldshift.api import app
from fieldshift.contracts import validate
from fieldshift.evaluator import evaluate, load_rules
from fieldshift.recommender.validation import validate_result_semantics

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "environment-ro-south.json"
TOKEN = "test-engine-token-with-at-least-32-characters"
BARAGAN = {"name": "Bărăgan test point", "latitude": 44.56, "longitude": 27.36}
# In Romania but outside the described southern zone. `run`/`cached_run` call
# `computed_result` with `load_rules` directly, so they exercise the "no rules at all" path
# (still reached in production when the provisional profile has no usable temperatures);
# the HTTP tests go through `pipeline.recommend`, which adds the provisional rules.
OUTSIDE = {"name": "Outside covered zones", "latitude": 47.2, "longitude": 23.0}
CROP_IDS = tuple(crop["id"] for crop in load_rules(BARAGAN)["crops"])


def excluded_except(*crop_ids: str) -> list[str]:
    return [crop_id for crop_id in CROP_IDS if crop_id not in crop_ids]


@lru_cache(maxsize=1)
def _raw() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def environment() -> dict:
    return json.loads(_raw())


def p2_built_environment(request: dict) -> dict:
    """Run P2's REAL `build_environment` offline.

    Only its three network calls are replaced: `fetch_power` returns the fixture in the
    shape `power.fetch_power` returns (daily `values` incl. T2MDEW, `elevation_m`), and
    SoilGrids/SRTM report themselves unavailable. P2's own daily cleaning, ET0, monthly
    climate and climate context code runs unchanged.
    """
    fx = environment()
    power = {
        "location": fx["location"],
        "period": fx["period"],
        "elevation_m": fx["static"]["elevation_m"],
        "daily": fx["daily"],
        "parameters": {},
        "sources": [s for s in fx["sources"] if s["id"] == "nasa-power"],
        "retrieved_at": fx["retrieved_at"],
        "data_gaps": [],
    }
    with (
        mock.patch.object(data_service, "fetch_power", lambda *args: power),
        mock.patch.object(
            data_service,
            "fetch_soil",
            lambda *args: (None, [], ["SoilGrids not queried (offline test)."]),
        ),
        mock.patch.object(
            data_service,
            "fetch_slope",
            lambda *args: (None, [], ["SRTM slope not queried (offline test)."]),
        ),
        mock.patch.object(
            data_service,
            "fetch_slopes",
            lambda points: (
                [None] * len(points),
                [],
                ["SRTM slope not queried (offline test)."],
            ),
        ),
        mock.patch.dict(os.environ, {"ENABLE_NASA_POWER": "true"}),
    ):
        return data_service.build_environment(request)


def dashboard_request(**changes) -> dict:
    """Shape built by field-dashboard.tsx analyse(): fixed water/soil/climate 3."""
    request = {
        "schema_version": "1.0",
        "location": dict(BARAGAN),
        "available_from": "2026-11-14",
        "crop_count": 3,
        "history": [{"crop_id": "maize", "source": "typed"}],
        "current_rotation": ["maize", "winter_wheat"],
        "soil": {"texture": "unknown", "source": "unknown"},
        "priorities": {"water": 3, "soil": 3, "climate": 3, "productivity": 0},
        "constraints": {"irrigated": False, "excluded_crops": []},
        "scenario": {"temp_change_c": 0, "rain_change_pct": 0},
    }
    request.update(copy.deepcopy(changes))
    assert not validate("recommendation-request", request)
    return request


def calculator_full_request() -> dict:
    """The shared full example the calculator loads, moved onto the fixture's point."""
    request = json.loads((ROOT / "packages/contracts/examples/recommendation-request.full.json").read_text(encoding="utf-8"))
    request["location"] = dict(BARAGAN)
    assert not validate("recommendation-request", request)
    return request


def run(request: dict, env: dict | None = None, request_id: str = "web-audit") -> dict:
    env = environment() if env is None else env
    return pipeline.computed_result(request, request_id, env, load_rules(request["location"]), evaluate)


@lru_cache(maxsize=16)
def _cached(request_json: str) -> str:
    return json.dumps(run(json.loads(request_json)))


def cached_run(request: dict) -> dict:
    return json.loads(_cached(json.dumps(request, sort_keys=True)))


def next_route_errors(request: dict, result: dict, request_id: str) -> list[str]:
    """Mirror of the post-checks in apps/web/src/lib/server/engine.ts `recommend()`.

    Keep in sync with that file; the Node harness checks the real handler."""
    errors = list(validate("recommendation-result", result)) + validate_result_semantics(result)
    if result.get("request_id") != request_id:
        errors.append("request_id does not echo X-Request-ID")
    loc = result.get("location", {})
    if loc.get("latitude") != request["location"]["latitude"] or loc.get("longitude") != request["location"]["longitude"]:
        errors.append("location mismatch")
    excluded = request["constraints"].get("excluded_crops", [])
    for plan in result.get("plans", []):
        for step in plan["steps"]:
            if step["sowing_window"]["start"] < request["available_from"]:
                errors.append("sowing before available_from")
            if step["crop_id"] in excluded:
                errors.append("excluded crop returned")
    if len(json.dumps(result).encode()) > 2_000_000:
        errors.append("result larger than the 2 MB Next.js limit")
    return errors


def user_texts(result: dict) -> list[str]:
    texts = [*result["assumptions"], *result["data_gaps"], result["disclaimer"]]
    for plan in result["plans"] + ([result["baseline"]] if "baseline" in result else []):
        texts += [plan["label"], plan["explanation"], *plan["benefits"], *plan["tradeoffs"]]
        texts += [*(plan.get("local_checks") or []), *(plan.get("violations") or [])]
        texts += [s["reason"] for s in plan["steps"]] + [s["crop_name"] for s in plan["steps"]]
    return texts


# --- Internal HTTP endpoint with real P3–P4 ------------------------------------------------


@pytest.fixture
def computed_client(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    monkeypatch.setenv("ENGINE_MODE", "computed")
    # P2's real build_environment with only its network calls replaced (see
    # p2_built_environment); P3 (load_rules, evaluate) and P4 are the real modules.
    monkeypatch.setattr(pipeline, "build_environment", p2_built_environment)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("make", [dashboard_request, calculator_full_request], ids=["dashboard", "calculator_full"])
def test_internal_api_returns_real_computed_results_that_pass_the_next_route_checks(computed_client, make):
    request = make()
    response = computed_client.post(
        "/recommendations",
        headers={"Authorization": "Bearer " + TOKEN, "X-Request-ID": "web-request-id"},
        json=request,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mode"] == "computed" and result["status"] == "complete"
    assert "baseline" in result, "both frontend shapes send current_rotation"
    assert next_route_errors(request, result, "web-request-id") == []


def test_internal_api_outside_described_zones_uses_disclosed_provisional_rules(computed_client):
    # Since PR #7, Romanian points outside the described southern zone get provisional
    # thermal-band rules (pipeline.recommend → load_provisional_romania_rules) instead of
    # `insufficient_data`; the profile reads P2's cleaned daily records (fixed in a372f41).
    # The fixture's (Bărăgan) weather stands in for this point's weather.
    request = dashboard_request(location=dict(OUTSIDE))
    response = computed_client.post(
        "/recommendations", headers={"Authorization": "Bearer " + TOKEN, "X-Request-ID": "outside"}, json=request
    )
    assert response.status_code == 200
    result = response.json()
    assert next_route_errors(request, result, "outside") == []
    assert result["plans"], "provisional rules supply candidate crops"
    disclosed = " ".join(result["assumptions"] + result["data_gaps"])
    assert "provisional" in disclosed and "not validated" in disclosed
    for plan in result["plans"]:
        assert plan["confidence"] == "low", "unvalidated provisional calendars cap confidence"
        assert "provisional regional rules" in plan["explanation"]


def test_internal_api_rejects_points_outside_romania_without_plans(computed_client):
    request = dashboard_request(location={"name": "Budapest", "latitude": 47.4979, "longitude": 19.0402})
    response = computed_client.post(
        "/recommendations", headers={"Authorization": "Bearer " + TOKEN, "X-Request-ID": "abroad"}, json=request
    )
    assert response.status_code == 422
    assert "plans" not in response.json()


# --- Priorities the frontend sends are the priorities P4 applies ---------------------------


def test_dashboard_fixed_priorities_are_what_p4_reports():
    result = cached_run(dashboard_request())
    # The dashboard's five 0–100 preview sliders are not sent; P4 sees water/soil/climate 3.
    assert "Priorities were normalized to: water 33%, soil 33%, climate 33%." in result["assumptions"]
    for plan in result["plans"]:
        assert "priorities as water 33%, soil 33%, climate 33%." in plan["explanation"]


def test_calculator_priorities_reach_p4_unchanged():
    request = calculator_full_request()
    p = request["priorities"]
    total = sum(v for v in p.values() if v)
    result = cached_run(request)
    expected = ", ".join(f"{k} {p[k] / total * 100:.0f}%" for k in ("water", "soil", "climate", "productivity") if p.get(k))
    assert f"Priorities were normalized to: {expected}." in result["assumptions"]


# --- User-facing text regressions found in the full-stack audit ----------------------------


@pytest.mark.parametrize(
    "request_",
    [
        dashboard_request(),
        dashboard_request(constraints={"irrigated": False, "excluded_crops": excluded_except("maize", "winter_rapeseed")}),
        dashboard_request(location=dict(OUTSIDE)),
        dashboard_request(current_rotation=["sunflower"]),
    ],
    ids=["complete", "limited_with_excluded_baseline_crop", "outside", "infeasible_baseline"],
)
def test_no_raw_crop_ids_or_doubled_punctuation_in_user_text(request_):
    result = cached_run(request_)
    for text in user_texts(result):
        for crop_id in CROP_IDS:
            if "_" in crop_id:
                assert crop_id not in text, f"raw crop id {crop_id!r} in: {text}"
        assert not re.search(r"\.\.(?!\.)|\.;|;\.", text), f"doubled punctuation in: {text}"


def test_limited_result_shape_and_excluded_baseline_crop_named():
    request = dashboard_request(
        constraints={
            "irrigated": False,
            "excluded_crops": excluded_except("maize", "winter_rapeseed"),
        }
    )
    result = cached_run(request)
    assert result["status"] == "limited" and 1 <= len(result["plans"]) <= 2
    assert next_route_errors(request, result, "web-audit") == []
    baseline = result["baseline"]
    assert "Includes crop(s) you excluded from the recommendations: Winter wheat." in baseline["tradeoffs"]


def test_current_rotation_comparison_never_shows_equal_numbers_as_different():
    found = False
    # The last request reproduced "Higher weighted score than your current rotation (0.55 vs 0.55)".
    rounding_case = dashboard_request(
        available_from="2026-10-01",
        history=[{"crop_id": "maize", "harvest_year": 2026, "source": "typed"}],
        priorities={"water": 3, "soil": 3, "climate": 3},
        constraints={
            "irrigated": False,
            "excluded_crops": excluded_except("maize", "winter_rapeseed"),
        },
    )
    for request in (dashboard_request(), calculator_full_request(), rounding_case):
        result = cached_run(request)
        for plan in result["plans"]:
            for line in plan["benefits"] + plan["tradeoffs"]:
                m = re.search(r"(Better|Worse) overall than your current rotation \(([\d.]+) vs ([\d.]+) out of 100\)", line)
                if m:
                    found = True
                    assert m.group(2) != m.group(3), line
    assert found, "at least one plan must be compared with the current rotation"


def test_explanation_points_to_local_checks_and_gaps_instead_of_repeating_them():
    result = cached_run(dashboard_request())
    for plan in result["plans"] + [result["baseline"]]:
        assert plan["local_checks"], "local checks are a structured field the UI lists"
        for check in plan["local_checks"]:
            assert check not in plan["explanation"]
        assert f"review the {len(plan['local_checks'])} local check" in plan["explanation"]
    # Every per-plan gap is still in the result-level list, so nothing is lost.
    assert "Elevation" not in " ".join(result["data_gaps"])  # fixture has elevation


def test_out_of_zone_gaps_are_not_repeated_and_the_rotation_is_named():
    result = cached_run(dashboard_request(location=dict(OUTSIDE)))
    gaps = result["data_gaps"]
    assert any("outside the zones that have regional crop rules" in g for g in gaps)
    assert "The regional rules contain no candidate crops." not in gaps
    assert any("Your current rotation (Maize → Winter wheat) could not be shown" in g for g in gaps)


# --- P2 adapter shape -----------------------------------------------------------------------


def test_p2_build_environment_output_is_accepted_without_et0_bias():
    request = dashboard_request()
    env = p2_built_environment(request)
    # PR #7 fixed the audit finding: dew point and elevation now reach the data, so every
    # day uses FAO-56 Penman-Monteith (no sea-level or Hargreaves fallback).
    assert env["static"]["elevation_m"] == environment()["static"]["elevation_m"]
    assert "slope_pct" not in env["static"]
    assert env["quality"]["et0_methods"]["hargreaves"] == 0
    assert env["quality"]["missing"]["dewpoint"] == 0
    result = run(request, env)
    assert next_route_errors(request, result, "web-audit") == []
    assert result["status"] == "complete" and "baseline" in result
    assert result["monthly_climate"] and "climate_context" in result
    assert not any("Elevation is missing" in g for g in result["data_gaps"])
    assert any("SoilGrids not queried" in g for g in result["data_gaps"]), "P2 gaps reach the farmer"
    reference = cached_run(request)
    shown = lambda r: [
        (tuple(step["crop_id"] for step in plan["steps"]), plan["scores"])
        for plan in r["plans"] + [r["baseline"]]
    ]
    assert shown(result) == shown(reference)


# --- Merge with PR #7: duplicate messages in the result --------------------------------------


def test_empty_result_is_explained_once():
    request = dashboard_request(
        constraints={"irrigated": False, "excluded_crops": list(CROP_IDS)}
    )
    result = cached_run(request)
    assert result["status"] == "insufficient_data"
    assert sum("feasible" in g and "plan" in g for g in result["data_gaps"]) == 1, result["data_gaps"]
    assert "No feasible rotation could be scored from the available observations and constraints." not in result["data_gaps"]


def test_crop_unknown_to_p3_is_listed_once():
    result = cached_run(dashboard_request(current_rotation=["maize", "rice"]))
    gaps = " ".join(result["data_gaps"])
    assert "Crops without regional rules: rice." in gaps and "rice, rice" not in gaps


def test_warnings_name_the_step_when_a_crop_repeats():
    result = cached_run(dashboard_request(
        constraints={
            "irrigated": False,
            "excluded_crops": excluded_except("maize", "winter_rapeseed"),
        }
    ))
    for plan in result["plans"]:
        crops = [s["crop_id"] for s in plan["steps"]]
        if crops.count("maize") > 1:
            maize = [t for t in plan["tradeoffs"] if t.startswith("Watch out: Maize")]
            assert maize and all(re.match(r"Watch out: Maize \(crop [123]\):", t) for t in maize), maize
            break
    else:
        pytest.fail("expected a plan with maize twice")
