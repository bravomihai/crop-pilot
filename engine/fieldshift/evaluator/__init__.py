"""P3: rotation evaluator. Scores ONE rotation on every criterion, without farmer priorities.

Criteria: suitability (EcoCrop), yield (GAEZ), water (FAO-56 Kc x ET0 vs rain/soil
moisture), soil, erosion (SRTM slope x bare months x heavy rain), pest_break,
succession (successor matrix), forage, income (market list).

Rules and crop tables live in engine/rules/<region>.crop-rules.json (CropRules format) and every
value needs a source.
"""

import json
from pathlib import Path

from ..contracts import CropRules, Evaluation, FarmRequest, FieldData, example

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


def load_rules(region: str = "ro-south") -> CropRules:
    """Load engine/rules/<region>.crop-rules.json, falling back to the contract example."""
    path = RULES_DIR / f"{region}.crop-rules.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return example("crop-rules")


def evaluate(
    rotation: list[str],
    farm: FarmRequest,
    field_data: FieldData,
    rules: CropRules,
    cover_crops: list[dict] | None = None,
) -> Evaluation:
    """Return an Evaluation for the rotation. Must validate against evaluation.schema.json.

    Use farm["scenario"] (and field_data["scenario_deltas"]) to adjust the weather years.
    Infeasible rotations still return a full Evaluation with feasible=False and violations.

    TODO(P3): real rule checks and scores.
    """
    result = example("evaluation")
    result["rotation"] = list(rotation)
    result["cover_crops"] = list(cover_crops or [])
    result["scenario"] = farm["scenario"]
    return result
