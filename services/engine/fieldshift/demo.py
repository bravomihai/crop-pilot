"""Fictional integration fixture. These windows and sequences are NOT sourced agronomy."""

from calendar import monthrange
from datetime import date, timedelta, datetime, timezone

CATALOG = {
    "pea": ("Pea", 3, 7),
    "maize": ("Maize", 4, 9),
    "winter_wheat": ("Winter wheat", 10, 7),
    "winter_barley": ("Winter barley", 10, 6),
    "sunflower": ("Sunflower", 4, 9),
    "oats": ("Oats", 3, 7),
    "sorghum": ("Grain sorghum", 5, 10),
    "dry_beans": ("Dry beans", 5, 9),
    "sugar_beet": ("Sugar beet", 3, 10),
    "spring_barley": ("Spring barley", 3, 7),
    "triticale": ("Triticale", 10, 7),
    "winter_rye": ("Winter rye", 10, 7),
    "potato": ("Potato", 4, 9),
}
SEQUENCES = [
    ("pea", "winter_wheat", "maize"),
    ("winter_wheat", "sunflower", "winter_barley"),
    ("winter_barley", "pea", "winter_wheat"),
    ("oats", "dry_beans", "sorghum"),
    ("sorghum", "sugar_beet", "oats"),
    ("dry_beans", "oats", "sugar_beet"),
    ("sugar_beet", "sorghum", "dry_beans"),
    ("spring_barley", "potato", "winter_rye"),
    ("triticale", "dry_beans", "spring_barley"),
    ("potato", "winter_rye", "triticale"),
    ("winter_rye", "potato", "sorghum"),
]


def demo_steps(sequence: tuple[str, ...], available: date) -> list[dict]:
    steps = []
    for index, crop in enumerate(sequence):
        name, sowing, harvest = CATALOG[crop]
        year = available.year
        if available > date(year, sowing, monthrange(year, sowing)[1]):
            year += 1
        start = max(available, date(year, sowing, 1))
        end = date(year, sowing, monthrange(year, sowing)[1])
        harvest_year = year + (harvest < sowing)
        harvest_start = date(harvest_year, harvest, 1)
        harvest_end = date(harvest_year, harvest, monthrange(harvest_year, harvest)[1])
        steps.append(
            {
                "order": index + 1,
                "crop_id": crop,
                "crop_name": name,
                "sowing_window": {"start": start.isoformat(), "end": end.isoformat()},
                "harvest_window": {
                    "start": harvest_start.isoformat(),
                    "end": harvest_end.isoformat(),
                },
                "reason": "Illustrative position in the plan; agronomic compatibility is not calculated.",
            }
        )
        available = harvest_end + timedelta(days=30)
    return steps


def recommend_demo(request: dict, request_id: str) -> dict:
    excluded = set(request["constraints"].get("excluded_crops", []))
    constraints = request["constraints"]
    selected = (
        set(constraints.get("selected_crops", []))
        if constraints.get("selected_crops_only", False)
        else None
    )
    sequences = [
        sequence
        for sequence in SEQUENCES
        if not excluded.intersection(sequence)
        and (selected is None or set(sequence).issubset(selected))
    ][:3]
    plans = []
    for index, sequence in enumerate(sequences):
        plans.append(
            {
                "id": f"demo-{index + 1}",
                "label": f"Demo plan {index + 1}",
                "steps": demo_steps(
                    sequence, date.fromisoformat(request["available_from"])
                ),
                "benefits": [
                    "Illustrates a sequence of three successive main crops."
                ],
                "tradeoffs": [
                    "The calendar is fictional and must be replaced with documented local windows.",
                    "Water, soil, and climate are not yet evaluated; the plan has no agronomic score.",
                ],
                "explanation": "An example for frontend and backend integration. Priorities and the scenario do not generate predictions in this mode.",
                "confidence": "low",
                "source_ids": ["demo-fixture"],
            }
        )
    return {
        "schema_version": "1.0",
        "request_id": request_id,
        "mode": "demo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete"
        if len(plans) == 3
        else "limited"
        if plans
        else "insufficient_data",
        "location": request["location"],
        "plans": plans,
        "monthly_climate": [],
        "assumptions": [
            "A fictional result for development, not an agronomic recommendation.",
            "Three successive main crops; the plan does not repeat automatically.",
            "Demo mode respects the start date and exclusions, but does not evaluate priorities, soil, or the scenario.",
        ],
        "data_gaps": [
            "The agronomic evaluation and optimization engine still needs to be implemented by P3/P4."
        ]
        + (
            []
            if request.get("history")
            else ["Crop history has not been provided."]
        ),
        "sources": [
            {
                "id": "demo-fixture",
                "title": "Fictional development data — no NASA observations",
            }
        ],
        "disclaimer": "Do not use these examples as cultivation instructions. Crop windows and compatibility require local verification.",
    }
