"""Regional rule files. One JSON file per agro-climatic zone; `load_rules` picks the zone."""

from __future__ import annotations

import copy
import json
import math
from calendar import monthrange
from datetime import date
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent
FIELD_SHIFT_DIR = RULES_DIR.parents[1]
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


@lru_cache
def _thermal_profile() -> dict:
    return json.loads(
        (FIELD_SHIFT_DIR / "crop_rules.json").read_text(encoding="utf-8")
    )


def _shift_month(value: str, offset: int) -> str:
    month, day = (int(part) for part in value.split("-"))
    absolute_month = month - 1 + offset
    year, month = divmod(absolute_month, 12)
    year += 2000
    month += 1
    day = min(day, monthrange(year, month)[1])
    return f"{month:02}-{day:02}"


def load_provisional_romania_rules(location: dict, environment: dict) -> dict:
    """Use the project thermal profile where no locally described zone exists."""
    profile = _thermal_profile()
    temperatures = []
    for entry in environment.get("daily", []):
        try:
            day = date.fromisoformat(entry["date"])
            temperature = float(entry["values"]["T2M"])
        except (KeyError, TypeError, ValueError):
            continue
        if day.month in range(4, 10) and math.isfinite(temperature):
            temperatures.append(temperature)
    if not temperatures:
        return {
            "region": None,
            "crops": [],
            "sources": [],
            "data_gaps": [
                "No usable April–September temperatures are available for the provisional Romania profile."
            ],
        }

    mean_temperature = sum(temperatures) / len(temperatures)
    bands = profile["region"]["thermal_bands"]
    zone_id = (
        "warm"
        if mean_temperature >= bands["warm"]["minimum_mean_apr_sep_c"]
        else "temperate"
        if mean_temperature >= bands["temperate"]["minimum_mean_apr_sep_c"]
        else "cool"
    )
    zone = bands[zone_id]
    rules = copy.deepcopy(_read("ro_south.json"))
    adjustment = profile["region"]["zone_adjustments"][zone_id]
    for crop in rules["crops"]:
        autumn = crop.get("winter", False) or int(crop["sowing"]["start"][:2]) >= 9
        offset = (
            adjustment["autumn_sowing_month_offset"]
            if autumn
            else adjustment["spring_sowing_month_offset"]
        )
        for key in ("start", "optimal_end", "latest"):
            crop["sowing"][key] = _shift_month(crop["sowing"][key], offset)
        for key in ("start", "end"):
            crop["harvest"][key] = _shift_month(crop["harvest"][key], offset)

    rules["region"] = {
        "id": f"ro-romania-provisional-{zone_id}",
        "name": f"Provisional Romania {zone['name']} thermal band",
        "thermal_band": zone["name"],
        "mean_apr_sep_t2m_c": round(mean_temperature, 1),
        "boxes": [],
    }
    rules.setdefault("assumptions", []).append(
        "Outside the locally described southern zone, crop rules use provisional project thermal-band calendar shifts; they are not validated Romanian regional recommendations."
    )
    rules["data_gaps"] = [
        "No local crop-rule profile is available for this region; the southern Romania crop catalog is used with a provisional climate-based calendar shift."
    ] + rules.get("data_gaps", [])
    profile_source_ids = {
        "romania-admin-boundary",
        "ro-thermal-bands",
        "romania-calendar-estimate",
    }
    sources = {source["id"]: source for source in rules.get("sources", [])}
    for source in profile["sources"]:
        if source["id"] in profile_source_ids:
            sources[source["id"]] = source
    rules["sources"] = list(sources.values())
    return rules
