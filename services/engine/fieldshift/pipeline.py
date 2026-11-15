"""Stateless boundary used by HTTP and future channel adapters."""

import os
from datetime import date, datetime, timezone

from .data_service import build_environment
from .demo import recommend_demo
from .evaluator import climate_context, evaluate, load_rules
from .evaluator.economics import add_economics
from .evaluator.rules import load_provisional_romania_rules
from .geography import validate_field_boundary, validate_location
from .recommender import recommend_rotations
from .recommender.validation import validate_result_semantics

DISCLAIMER = (
    "Estimates for exploring options. Verify crop compatibility, the calendar "
    "and the assumptions locally before applying any plan."
)
FIELD_DATA_GAP = (
    "The field boundary is included in the request, but climate and soil data "
    "are sampled at its representative point rather than aggregated across the field."
)


def start_from_today(request: dict, today: date | None = None) -> tuple[dict, str | None]:
    """A past availability date would produce plans in the past: start from today instead."""
    today = today or date.today()
    given = date.fromisoformat(request["available_from"])
    if given >= today:
        return request, None
    note = (
        f"The field availability date ({given.isoformat()}) is in the past; the plans start "
        f"from today ({today.isoformat()})."
    )
    return {**request, "available_from": today.isoformat()}, note


def recommend(request: dict, request_id: str) -> dict:
    request, note = start_from_today(request)
    result = _recommend_mode(request, request_id)
    if note:
        result["assumptions"] = [note] + result["assumptions"]
    return result


def _recommend_mode(request: dict, request_id: str) -> dict:
    mode = os.getenv("ENGINE_MODE", "demo")
    if mode == "demo":
        return recommend_demo(request, request_id)
    if mode != "computed":
        raise ValueError("Unknown ENGINE_MODE")
    validate_location(request["location"])
    if request.get("field_boundary"):
        validate_field_boundary(request["field_boundary"], request["location"])
    environment = build_environment(request)
    rules = load_rules(request["location"])
    if not rules.get("crops"):
        rules = load_provisional_romania_rules(request["location"], environment)
    return computed_result(request, request_id, environment, rules, evaluate)


def computed_result(
    request: dict, request_id: str, environment: dict, rules: dict, evaluate
) -> dict:
    """Combine the NASA data summary with P3 evidence and P4 rotation plans."""
    # P4's outcome already carries the data gaps of the shown plans, the baseline and,
    # for an empty result, the gaps common to every evaluated sequence. Copying the gaps
    # of all evaluated sequences here flooded results with per-sequence variants.
    plans = recommend_rotations(request, environment, rules, evaluate)
    outcome = getattr(plans, "outcome", None)
    if outcome is not None and outcome.fixture:
        raise NotImplementedError("Fixture evaluations cannot back computed mode")
    plans = list(plans)

    assumptions = (
        list(environment.get("assumptions", []))
        + list(rules.get("assumptions", []))
        + (outcome.assumptions if outcome else [])
    )
    data_gaps = (
        list(environment.get("data_gaps", []))
        + list(rules.get("data_gaps", []))
        + (outcome.data_gaps if outcome else [])
    )
    if request.get("field_boundary"):
        data_gaps.append(FIELD_DATA_GAP)
    if not plans and outcome is None:
        # The P4 outcome already explains an empty result; only plain-list callers need this.
        data_gaps.append(
            "No feasible rotation could be scored from the available observations and constraints."
        )

    sources = (
        outcome.sources
        if outcome
        else list(environment.get("sources", [])) + list(rules.get("sources", []))
    )
    result = {
        "schema_version": "1.0",
        "request_id": request_id,
        "mode": "computed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": outcome.status if outcome else (
            "complete" if len(plans) == 3 else "limited" if plans else "insufficient_data"
        ),
        "location": request["location"],
        "plans": plans,
        "monthly_climate": environment.get("monthly_climate", []),
        "assumptions": list(dict.fromkeys(assumptions)),
        "data_gaps": list(dict.fromkeys(data_gaps)),
        "sources": sources,
        "disclaimer": DISCLAIMER,
    }
    if outcome is not None and outcome.baseline is not None:
        result["baseline"] = outcome.baseline
    climate = environment.get("climate_context")
    if climate is None:
        climate = climate_context(environment, request["location"])
    if climate is not None:
        listed = {source["id"] for source in result["sources"]}
        climate["source_ids"] = [i for i in climate["source_ids"] if i in listed]
        result["climate_context"] = climate
    try:
        add_economics(result, request)
    except Exception:  # optional estimate: never block the agronomic result
        result["data_gaps"].append("Money estimate unavailable because of an internal error.")
        for plan in result["plans"] + ([result["baseline"]] if result.get("baseline") else []):
            plan.pop("economics", None)
    errors = validate_result_semantics(result)
    if errors:
        raise RuntimeError(
            "Recommendation result failed semantic checks: " + "; ".join(errors)
        )
    return result
