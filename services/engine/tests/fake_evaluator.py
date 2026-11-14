"""FAKE P3 evaluator for testing the P4 recommendation ALGORITHM only.

Every crop, month and score below is synthetic. None of it is agronomic knowledge, a
regional calendar or NASA data. Outputs are marked `"fixture": True` so the pipeline
refuses to present them as computed results. Tests built on this module verify search,
ranking, selection and validation logic, not scientific correctness.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

FAKE_SOURCE = {"id": "fake-p3", "title": "Synthetic test evaluator — no agronomic value"}

# crop_id: (display name, sowing month start, sowing month end, harvest month, scores)
FAKE_CROPS = {
    "alpha": ("Alpha (synthetic)", 3, 4, 7, {"water": 0.9, "soil": 0.4, "climate": 0.6}),
    "beta": ("Beta (synthetic)", 4, 5, 9, {"water": 0.3, "soil": 0.8, "climate": 0.5}),
    "gamma": ("Gamma (synthetic, autumn)", 10, 10, 7, {"water": 0.6, "soil": 0.6, "climate": 0.9}),
    "delta": ("Delta (synthetic, autumn)", 9, 10, 6, {"water": 0.5, "soil": 0.5, "climate": 0.4}),
    "epsilon": ("Epsilon (synthetic)", 4, 4, 8, {"water": 0.2, "soil": 0.3, "climate": 0.2}),
}


def fake_rules(crops=None) -> dict:
    crops = crops or sorted(FAKE_CROPS)
    return {
        "crops": [{"id": c, "name": FAKE_CROPS[c][0]} for c in crops],
        "sources": [FAKE_SOURCE],
    }


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def fake_calendar(rotation, available: date) -> list[dict]:
    steps, cursor = [], available
    for crop in rotation:
        name, sm, em, hm, _ = FAKE_CROPS[crop]
        year = cursor.year
        while _month_end(year, em) < cursor:
            year += 1
        sow_start = max(cursor, date(year, sm, 1))
        sow_end = _month_end(year, em)
        hy = year + (hm < sm)
        harvest_start, harvest_end = date(hy, hm, 1), _month_end(hy, hm)
        steps.append(
            {
                "crop_id": crop,
                "crop_name": name,
                "sowing_window": {"start": sow_start.isoformat(), "end": sow_end.isoformat()},
                "harvest_window": {"start": harvest_start.isoformat(), "end": harvest_end.isoformat()},
                "source_ids": ["fake-p3"],
            }
        )
        cursor = harvest_end + timedelta(days=1)
    return steps


class FakeEvaluator:
    """Configurable synthetic evaluator.

    - `forbid_repeat`: consecutive identical crops are infeasible (synthetic rule).
    - `forbid_after_history`: first crop equal to the latest history crop is infeasible.
    - `missing`: criteria returned as unknown (score None).
    - `unknown_for`: rotations returned with feasibility "unknown".
    - `scenario_aware`: applies a synthetic climate shift and sets scenario_applied.
    """

    def __init__(
        self,
        forbid_repeat=True,
        forbid_after_history=True,
        missing=(),
        missing_for=None,
        unknown_for=(),
        scenario_aware=False,
        overrides=None,
        fixture=True,
    ):
        self.forbid_repeat = forbid_repeat
        self.forbid_after_history = forbid_after_history
        self.missing = set(missing)
        self.missing_for = missing_for or {}
        self.unknown_for = {tuple(r) for r in unknown_for}
        self.scenario_aware = scenario_aware
        self.overrides = overrides or {}
        self.fixture = fixture
        self.calls: list[tuple[tuple[str, ...], dict]] = []

    def __call__(self, rotation, request, environment, rules):
        rotation = tuple(rotation)
        self.calls.append((rotation, request.get("scenario")))
        if rotation in self.overrides:
            return self.overrides[rotation]
        base = {"source_ids": ["fake-p3"], "fixture": self.fixture, "scenario_applied": self.scenario_aware}
        if rotation in self.unknown_for:
            return {**base, "feasibility": "unknown", "data_gaps": ["synthetic: missing data"]}
        violations = []
        if self.forbid_repeat and any(a == b for a, b in zip(rotation, rotation[1:])):
            violations.append("synthetic: same crop twice in a row")
        history = request.get("history") or []
        if self.forbid_after_history and history and history[-1]["crop_id"] == rotation[0]:
            violations.append("synthetic: same crop as the previous one")
        if violations:
            return {**base, "feasibility": "infeasible", "violations": violations}
        temp = (request.get("scenario") or {}).get("temp_change_c", 0)
        missing = self.missing | set(self.missing_for.get(rotation, ()))
        criteria = {}
        for name in ("water", "soil", "climate"):
            if name in missing:
                criteria[name] = {"score": None, "basis": "assumed"}
                continue
            value = sum(FAKE_CROPS[c][4][name] for c in rotation) / len(rotation)
            if self.scenario_aware and name == "climate":
                # Synthetic penalty for autumn crops only, so rankings can change.
                autumn = sum(FAKE_CROPS[c][1] >= 9 for c in rotation)
                value = min(1.0, max(0.0, value - 0.1 * temp * autumn / 3))
            criteria[name] = {
                "score": round(value, 6),
                "basis": "derived",
                "summary": "synthetic value",
                "source_ids": ["fake-p3"],
            }
        return {
            **base,
            "feasibility": "feasible",
            "criteria": criteria,
            "calendar": fake_calendar(rotation, date.fromisoformat(request["available_from"])),
            "warnings": [],
            "sources": [FAKE_SOURCE],
            "scenario_applied": self.scenario_aware,
        }
