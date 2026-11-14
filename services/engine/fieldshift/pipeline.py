"""Stateless boundary used by HTTP and future channel adapters."""

import os
from datetime import datetime, timezone
from .demo import recommend_demo
from .data_service import build_environment
from .evaluator import load_rules, evaluate
from .recommender import recommend_rotations


def recommend(request: dict, request_id: str) -> dict:
    mode = os.getenv("ENGINE_MODE", "demo")
    if mode == "demo":
        return recommend_demo(request, request_id)
    if mode != "computed":
        raise ValueError("Unknown ENGINE_MODE")
    environment = build_environment(request)
    rules = load_rules(request["location"])
    plans = recommend_rotations(request, environment, rules, evaluate)
    return {
        "schema_version": "1.0",
        "request_id": request_id,
        "mode": "computed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete"
        if len(plans) == 3
        else "limited"
        if plans
        else "insufficient_data",
        "location": request["location"],
        "plans": plans,
        "assumptions": environment.get("assumptions", []),
        "data_gaps": environment.get("data_gaps", []),
        "sources": environment["sources"] + rules.get("sources", []),
        "disclaimer": "Estimări pentru explorarea opțiunilor. Verifică local compatibilitățile, calendarul și ipotezele înainte de aplicare.",
    }
