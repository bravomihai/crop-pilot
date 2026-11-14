"""Regional rule files. One JSON file per agro-climatic zone; `load_rules` picks the zone."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent
REGION_FILES = ("ro_south.json",)


@lru_cache
def _read(name: str) -> dict:
    return json.loads((RULES_DIR / name).read_text(encoding="utf-8"))


def region_for(latitude: float, longitude: float) -> dict | None:
    for name in REGION_FILES:
        rules = _read(name)
        for box in rules["region"]["boxes"]:
            if box["lat"][0] <= latitude <= box["lat"][1] and box["lon"][0] <= longitude <= box["lon"][1]:
                return rules
    return None


def load_rules(location: dict) -> dict:
    """Rules for the zone containing the point. Outside every covered zone, no crops.

    An empty crop list makes the recommender answer `insufficient_data` instead of
    applying rules from another climate.
    """
    rules = region_for(float(location["latitude"]), float(location["longitude"]))
    if rules is None:
        covered = [_read(name)["region"]["name"] for name in REGION_FILES]
        return {
            "region": None,
            "crops": [],
            "sources": [],
            "data_gaps": [
                "This location is outside the zones that have regional crop rules ("
                + "; ".join(covered)
                + "). No rotation was evaluated."
            ],
        }
    return copy.deepcopy(rules)
