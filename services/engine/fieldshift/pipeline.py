"""Stateless boundary used by HTTP and future channel adapters."""

import os
from datetime import datetime, timezone
from .demo import recommend_demo
from .data_service import build_environment
from .evaluator import load_rules, evaluate
from .recommender import recommend_rotations
from .recommender.validation import validate_result_semantics

DISCLAIMER = "Estimates for exploring options. Verify crop compatibility, the calendar and the assumptions locally before applying any plan."


def recommend(request: dict, request_id: str) -> dict:
    mode = os.getenv("ENGINE_MODE", "demo")
    if mode == "demo":
        return recommend_demo(request, request_id)
    if mode != "computed":
        raise ValueError("Unknown ENGINE_MODE")
    environment = build_environment(request)
    rules = load_rules(request["location"])
    return computed_result(request, request_id, environment, rules, evaluate)


def computed_result(request: dict, request_id: str, environment: dict, rules: dict, evaluate) -> dict:
    """Assemble a computed-mode result from the real P2/P3 outputs and the P4 engine.

    Calls the team interface `recommend_rotations`. The P4 engine returns a PlanList whose
    `.outcome` adds P4 sources, assumptions, data gaps and the optional `baseline`. Any
    other implementation (or a test stub) returning a plain list gets the original
    assembly from the environment and rules metadata.
    """
    plans = recommend_rotations(request, environment, rules, evaluate)
    outcome = getattr(plans, "outcome", None)
    if outcome is not None and outcome.fixture:
        # Test/demo evaluations must never be presented as computed agronomy.
        raise NotImplementedError("Fixture evaluations cannot back computed mode")
    plans = list(plans)
    result = {
        "schema_version": "1.0",
        "request_id": request_id,
        "mode": "computed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if len(plans) == 3 else "limited" if plans else "insufficient_data",
        "location": request["location"],
        "plans": plans,
        "assumptions": list(environment.get("assumptions", [])) + (outcome.assumptions if outcome else []),
        "data_gaps": list(environment.get("data_gaps", [])) + (outcome.data_gaps if outcome else []),
        "sources": outcome.sources if outcome else list(environment.get("sources", [])) + list(rules.get("sources", [])),
        "disclaimer": DISCLAIMER,
    }
    if outcome is not None and outcome.baseline is not None:
        result["baseline"] = outcome.baseline
    errors = validate_result_semantics(result)
    if errors:
        raise RuntimeError("Recommendation result failed semantic checks: " + "; ".join(errors))
    return result
