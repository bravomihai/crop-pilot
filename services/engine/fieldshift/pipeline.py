"""Stateless boundary used by HTTP and future channel adapters."""

import os
from datetime import datetime, timezone

from .data_service import build_environment
from .demo import recommend_demo
from .evaluator import climate_context, evaluate, load_rules
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


def recommend(request: dict, request_id: str) -> dict:
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
    evaluation_gaps = []

    def evaluate_candidate(rotation, farm, data, crop_rules):
        result = evaluate(rotation, farm, data, crop_rules)
        evaluation_gaps.extend(result.get("data_gaps", []))
        return result

    plans = recommend_rotations(
        request, environment, rules, evaluate_candidate
    )
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
        + evaluation_gaps
        + (outcome.data_gaps if outcome else [])
    )
    if request.get("field_boundary"):
        data_gaps.append(FIELD_DATA_GAP)
    if not plans:
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
    climate = climate_context(environment, request["location"])
    if climate is not None:
        listed = {source["id"] for source in result["sources"]}
        climate["source_ids"] = [i for i in climate["source_ids"] if i in listed]
        result["climate_context"] = climate
    errors = validate_result_semantics(result)
    if errors:
        raise RuntimeError(
            "Recommendation result failed semantic checks: " + "; ".join(errors)
        )
    return result
