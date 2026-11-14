"""Stateless boundary used by HTTP and future channel adapters."""

import os
from datetime import datetime, timezone
from .demo import recommend_demo
from .data_service import build_environment
from .evaluator import load_rules, evaluate
from .recommender import recommend as recommend_plans
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
    """Assemble a computed-mode result from the real P2/P3 outputs and the P4 engine."""
    outcome = recommend_plans(request, environment, rules, evaluate)
    if outcome.fixture:
        # Test/demo evaluations must never be presented as computed agronomy.
        raise NotImplementedError("Fixture evaluations cannot back computed mode")
    result = {
        "schema_version": "1.0",
        "request_id": request_id,
        "mode": "computed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": outcome.status,
        "location": request["location"],
        "plans": outcome.plans,
        "assumptions": list(environment.get("assumptions", [])) + outcome.assumptions,
        "data_gaps": list(environment.get("data_gaps", [])) + outcome.data_gaps,
        "sources": outcome.sources,
        "disclaimer": DISCLAIMER,
    }
    errors = validate_result_semantics(result)
    if errors:
        raise RuntimeError("Recommendation result failed semantic checks: " + "; ".join(errors))
    return result
