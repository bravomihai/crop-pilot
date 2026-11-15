"""Weather hazards, temperature suitability and the soil index for a placed rotation."""

from __future__ import annotations

from datetime import date

from .schedule import Step
from .weather import Weather

HAZARD_LABELS = {
    "heat": "heat above {tmax_c} °C during flowering and grain fill",
    "winterkill": "winter frost below {tmin_c} °C (no snow-cover data)",
    "flowering_frost": "frost below {tmin_c} °C during flowering",
    "seedling_frost": "frost below {tmin_c} °C after emergence",
    "sowing_drought": "less than {rain_mm} mm of rain around sowing",
    "maturity": "not enough warmth to mature (needs {gdd_required} growing degree days)",
}


def _stage_range(bounds, stages) -> list[tuple[int, int]]:
    sow, b1, b2, b3, end = bounds
    spans = {"ini": (sow, b1), "dev": (b1, b2), "mid": (b2, b3), "late": (b3, end)}
    return [spans[s] for s in stages]


def hazards(weather: Weather, months: list[int], crop: dict, bounds) -> dict[str, dict]:
    """Hazard index (0 = none, 1 = severe) and the observed quantity, per hazard."""
    sow, _, _, _, end = bounds
    tmin, tmax, tmean, precip = weather.tmin, weather.tmax, weather.tmean, weather.precip
    size = len(weather)
    result: dict[str, dict] = {}
    for name, spec in (crop.get("hazards") or {}).items():
        if name == "heat":
            days = sum(
                1 for a, b in _stage_range(bounds, spec["stages"]) for i in range(a, b) if tmax[i] > spec["tmax_c"]
            )
            # Heat lowers yield but rarely destroys a crop: the index is capped by `severity`.
            result[name] = {
                "index": spec.get("severity", 0.5) * min(1.0, days / spec["severe_days"]),
                "value": days,
                "event": days >= spec["severe_days"] / 2,
            }
        elif name == "winterkill":
            days = sum(1 for i in range(sow, end) if months[i] in spec["months"] and tmin[i] <= spec["tmin_c"])
            result[name] = {"index": spec["severity"] if days else 0.0, "value": days, "event": days > 0}
        elif name == "flowering_frost":
            days = sum(
                1 for a, b in _stage_range(bounds, spec["stages"]) for i in range(a, b) if tmin[i] <= spec["tmin_c"]
            )
            result[name] = {"index": spec["severity"] if days else 0.0, "value": days, "event": days > 0}
        elif name == "seedling_frost":
            a, b = spec["days_after_sowing"]
            days = sum(1 for i in range(sow + a, min(sow + b, end)) if tmin[i] <= spec["tmin_c"])
            result[name] = {"index": spec["severity"] if days else 0.0, "value": days, "event": days > 0}
        elif name == "sowing_drought":
            a, b = max(0, sow - spec["days_before"]), min(size, sow + spec["days_after"])
            rain = sum(precip[a:b])
            short = max(0.0, 1.0 - rain / spec["rain_mm"])
            result[name] = {"index": spec["severity"] * short, "value": round(rain, 1), "event": rain < spec["rain_mm"]}
        elif name == "maturity":
            base, cap = spec["gdd_base_c"], spec["gdd_cap_c"]
            gdd = sum(min(max(tmean[i], base), cap) - base for i in range(sow, end))
            deficit = max(0.0, 1.0 - gdd / spec["gdd_required"])
            result[name] = {
                "index": spec["severity"] * min(1.0, deficit / 0.1),
                "value": round(gdd),
                "event": gdd < spec["gdd_required"],
            }
    return result


def combined_risk(found: dict[str, dict]) -> float:
    safe = 1.0
    for item in found.values():
        safe *= 1.0 - item["index"]
    return 1.0 - safe


def ramp(value: float, absolute: list[float], optimal: list[float]) -> float:
    """EcoCrop suitability: 1 inside the optimal range, 0 outside the absolute range."""
    lo_abs, hi_abs = absolute
    lo_opt, hi_opt = optimal
    if value <= lo_abs or value >= hi_abs:
        return 0.0
    if value < lo_opt:
        return (value - lo_abs) / (lo_opt - lo_abs)
    if value > hi_opt:
        return (hi_abs - value) / (hi_abs - hi_opt)
    return 1.0


def temperature_suitability(weather: Weather, crop: dict, bounds) -> tuple[float, float]:
    """EcoCrop temperature suitability over mid-season and late season, and that mean temperature."""
    _, _, b2, _, end = bounds
    values = weather.tmean[b2:end]
    mean = sum(values) / len(values)
    return ramp(mean, crop["ecocrop"]["tabs"], crop["ecocrop"]["topt"]), mean


def ph_suitability(ph: float | None, crop: dict) -> float | None:
    if ph is None:
        return None
    return ramp(ph, crop["ecocrop"]["ph_abs"], crop["ecocrop"]["ph_opt"])


def soil_index(
    steps: list[Step],
    classes: list[str | None],
    crops: dict,
    rules: dict,
    slope_pct: float | None,
    field_free: date | None = None,
) -> dict:
    """Rule-based soil index (0–1) from succession, diversity, cover and residue.

    An expert index, not a measurement: the weights live in the rules file and are listed
    there as pending agronomist review.
    """
    settings = rules["settings"]
    values = settings["successor_soil_value"]
    known = [values[c] for c in classes if c is not None]
    succession = sum(known) / len(known) if known else None

    ids = [s.crop_id for s in steps]
    families = {crops[c]["family"] for c in ids}
    family_score = {1: 0.0, 2: 0.6}.get(len(families), 1.0)
    legume = any(crops[c]["legume"] for c in ids)
    diversity = 0.6 * family_score + 0.4 * (1.0 if legume else 0.0)

    # The field is bare from the day it becomes free (`available_from`) until the first
    # sowing, not only between crops: a plan that waits most of a year for its first crop
    # must not look as well covered as one that starts at once.
    start = field_free if field_free is not None and field_free < steps[0].sow_date else steps[0].sow_date
    initial_bare_days = (steps[0].sow_date - start).days
    total_days = (steps[-1].harvest_date - start).days
    bare_days = initial_bare_days + sum((b.sow_date - a.harvest_date).days for a, b in zip(steps, steps[1:]))
    cover = 1.0 - bare_days / total_days if total_days > 0 else 0.0

    residue = sum(crops[c]["residue"] for c in ids) / len(ids)

    weights = dict(settings["soil_index_weights"])
    parts = {"succession": succession, "diversity": diversity, "cover": cover, "residue": residue}
    if slope_pct is not None:
        # Erosion exposure grows with slope and with the share of time the soil is bare.
        parts["erosion"] = 1.0 - min(1.0, slope_pct / 12.0) * (1.0 - cover)
        weights["erosion"] = settings["erosion_weight_when_slope_known"]
    used = {k: v for k, v in parts.items() if v is not None}
    weight_sum = sum(weights[k] for k in used)
    score = sum(weights[k] * v for k, v in used.items()) / weight_sum if weight_sum else None
    return {
        "score": score,
        "components": {k: (None if v is None else round(v, 3)) for k, v in parts.items()},
        "bare_days": bare_days,
        "initial_bare_days": initial_bare_days,
        "total_days": total_days,
        "legume": legume,
        "families": sorted(families),
    }
