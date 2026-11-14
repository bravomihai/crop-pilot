"""Fictional integration fixture. These windows and sequences are NOT sourced agronomy."""

from calendar import monthrange
from datetime import date, timedelta, datetime, timezone

CATALOG = {
    "pea": ("Mazăre", 3, 7),
    "maize": ("Porumb", 4, 9),
    "winter_wheat": ("Grâu de toamnă", 10, 7),
    "winter_barley": ("Orz de toamnă", 10, 6),
    "sunflower": ("Floarea-soarelui", 4, 9),
}
SEQUENCES = [
    ("pea", "winter_wheat", "maize"),
    ("winter_wheat", "sunflower", "winter_barley"),
    ("winter_barley", "pea", "winter_wheat"),
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
                "reason": "Poziție ilustrativă în plan; compatibilitatea agronomică nu este calculată.",
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
    ]
    plans = []
    for index, sequence in enumerate(sequences):
        plans.append(
            {
                "id": f"demo-{index + 1}",
                "label": f"Plan demonstrativ {index + 1}",
                "steps": demo_steps(
                    sequence, date.fromisoformat(request["available_from"])
                ),
                "benefits": [
                    "Ilustrează prezentarea unei succesiuni de trei culturi principale."
                ],
                "tradeoffs": [
                    "Calendarul este fictiv și trebuie înlocuit cu ferestre locale documentate.",
                    "Apa, solul și clima nu sunt încă evaluate; planul nu are un scor agronomic.",
                ],
                "explanation": "Exemplu pentru integrarea interfeței și a backendului. Prioritățile și scenariul nu generează predicții în acest mod.",
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
            "Rezultat fictiv pentru dezvoltare, nu recomandare agronomică.",
            "Trei culturi principale succesive; nu presupune repetarea automată a planului.",
            "Modul demo respectă data de pornire și excluderile, dar nu evaluează prioritățile, solul sau scenariul.",
        ],
        "data_gaps": [
            "Motorul de evaluare și optimizare agronomică trebuie implementat de P3/P4."
        ]
        + (
            []
            if request.get("history")
            else ["Istoricul culturilor nu a fost completat."]
        ),
        "sources": [
            {
                "id": "demo-fixture",
                "title": "Date fictive pentru dezvoltare — fără observații NASA",
            }
        ],
        "disclaimer": "Nu utiliza aceste exemple drept instrucțiuni de cultivare. Ferestrele și compatibilitățile necesită verificare locală.",
    }
