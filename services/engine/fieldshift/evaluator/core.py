"""Evaluate one rotation: calendar, rules, replay over past seasons, four criteria.

Output shape (read by `recommender/evaluation.py`, extra keys are ignored there):
  feasibility, violations, criteria{water, soil, climate, productivity}, calendar,
  warnings, local_checks, data_gaps, assumptions, source_ids, sources,
  scenario_applied, fixture, details (per-step evidence), replay (per-season results).

Scores are 0–1, higher is better for the farmer:
  water         FAO-56 daily soil water balance; relative yield from water, FAO-33 Ky.
  climate       heat, frost, winterkill, sowing drought, maturity; EcoCrop temperature fit.
  soil          rule-based index: succession, crop families and legumes, cover, residues.
  productivity  relative potential: water, weather, succession, sowing date, soil pH.
Season scores are combined as 0.7 × mean + 0.3 × the 20th percentile, so plans that fail
in bad years score lower than their average suggests.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import schedule, scoring, water
from .weather import Weather, build_weather

ROBUST_MEAN_WEIGHT = 0.7
ROBUST_LOW_WEIGHT = 0.3
LOW_PERCENTILE = 0.2
CACHE_SIZE = 8


@dataclass
class _WeatherEntry:
    """Everything computed from one environment object under one scenario.

    `environment` is a strong reference: while the entry is cached, no other object can
    get the same id(), and every lookup also checks identity, so a new request can never
    be served another request's weather. Replay and hazard results live inside the entry
    and are evicted with it.
    """

    environment: dict
    weather: Weather | None
    months: list[int] | None
    replay: dict = field(default_factory=dict)
    hazards: dict = field(default_factory=dict)


_weather_cache: "OrderedDict[tuple, _WeatherEntry]" = OrderedDict()
_cache_lock = threading.Lock()


# ---------------------------------------------------------------- environment adapters


def _static(environment: dict) -> dict:
    static = environment.get("static") if isinstance(environment.get("static"), dict) else {}
    return static


def _elevation(environment: dict) -> float | None:
    for holder in (_static(environment), environment, environment.get("location") or {}):
        for key in ("elevation_m", "elevation"):
            value = holder.get(key) if isinstance(holder, dict) else None
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _env_soil(environment: dict) -> dict:
    soil = _static(environment).get("soil") or environment.get("soil") or {}
    return soil if isinstance(soil, dict) else {}


def _slope(environment: dict) -> float | None:
    for key in ("slope_pct", "slope_percent"):
        value = _static(environment).get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _texture_from_fractions(soil: dict) -> str | None:
    clay, sand = soil.get("clay_pct"), soil.get("sand_pct")
    if not isinstance(clay, (int, float)) or not isinstance(sand, (int, float)):
        return None
    if clay >= 35:
        return "clay"
    if sand >= 70:
        return "sandy"
    silt = soil.get("silt_pct", 100 - clay - sand)
    if isinstance(silt, (int, float)) and silt >= 50:
        return "silty"
    return "loamy"


def _soil_inputs(request: dict, environment: dict, settings: dict) -> dict:
    farmer = request.get("soil") or {}
    regional = _env_soil(environment)
    farmer_source = farmer.get("source", "unknown")
    texture, texture_from = farmer.get("texture"), "farmer"
    if texture in (None, "unknown"):
        texture, texture_from = regional.get("texture") or _texture_from_fractions(regional), "regional"
    if texture in (None, "unknown"):
        texture, texture_from = None, None
    awc = regional.get("awc_m3_m3") if texture_from == "regional" else None
    if not isinstance(awc, (int, float)):
        awc = settings["awc_m3_m3"][texture or "unknown"]
    ph, ph_from = farmer.get("ph"), "farmer"
    if not isinstance(ph, (int, float)):
        ph, ph_from = regional.get("ph"), "regional"
    if not isinstance(ph, (int, float)):
        ph, ph_from = None, None
    return {
        "texture": texture,
        "texture_from": texture_from,
        "farmer_source": farmer_source,
        "awc": float(awc),
        "ph": None if ph is None else float(ph),
        "ph_from": ph_from,
    }


def _env_sources(environment: dict) -> list[dict]:
    """Environment sources in the contract shape. A missing title falls back to the dataset name."""
    found = []
    for source in environment.get("sources") or []:
        if not isinstance(source, dict) or not source.get("id"):
            continue
        clean = {"id": str(source["id"]), "title": str(source.get("title") or source.get("dataset") or source["id"])}
        url = source.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            clean["url"] = url
        if isinstance(source.get("resolution"), str):
            clean["resolution"] = source["resolution"]
        found.append(clean)
    return found


def _weather(environment: dict, latitude: float, elevation: float, temp: float, rain: float) -> _WeatherEntry:
    key = (id(environment), latitude, elevation, temp, rain)
    with _cache_lock:
        entry = _weather_cache.get(key)
        if entry is not None and entry.environment is environment:
            _weather_cache.move_to_end(key)
            return entry
    weather = build_weather(environment, latitude, elevation, temp, rain)
    months = None
    if weather is not None:
        months = [(weather.start + timedelta(days=i)).month for i in range(len(weather))]
    entry = _WeatherEntry(environment, weather, months)
    with _cache_lock:
        _weather_cache[key] = entry
        _weather_cache.move_to_end(key)
        while len(_weather_cache) > CACHE_SIZE:
            _weather_cache.popitem(last=False)
    return entry


# ---------------------------------------------------------------- replay


def _windows(weather: Weather, first: date, last: date, max_windows: int) -> list[int]:
    """Year shifts k such that the plan, moved k years back, lies inside the record."""
    shifts = []
    for k in range(0, first.year - weather.start.year + 1):
        if schedule.shift_years(first, k) >= weather.start and schedule.shift_years(last, k) <= weather.end:
            shifts.append(k)
    return shifts[:max_windows]


def _replay(
    prefix: tuple[str, ...],
    crops: dict,
    rules: dict,
    entry: _WeatherEntry,
    available_from: date,
    awc: float,
    irrigated: bool,
    budget: float | None,
) -> dict:
    """Calendar and per-season water results for a rotation prefix, memoised by prefix.

    Plans that share their first crops share that part of the computation.
    """
    key = (id(rules), available_from, awc, irrigated, budget, prefix)
    cached = entry.replay.get(key)
    if cached is not None and cached["rules"] is rules:
        return cached
    weather = entry.weather
    settings = rules["settings"]
    crop = crops[prefix[-1]]
    if len(prefix) == 1:
        parent = None
        step = schedule.place_next(crop, None, available_from, settings)
        steps = [step]
        start = available_from
        runs = {}
        initial = water.initial_state(awc, settings)
        for k in _windows(weather, available_from, step.harvest_end, 10**6):
            runs[k] = {"soil": initial, "seasons": [], "cursor": start}
    else:
        parent = _replay(prefix[:-1], crops, rules, entry, available_from, awc, irrigated, budget)
        step = schedule.place_next(crop, parent["steps"][-1], available_from, settings)
        steps = parent["steps"] + [step]
        runs = {}
        for k, run in parent["runs"].items():
            if schedule.shift_years(step.harvest_end, k) <= weather.end:
                runs[k] = run
    new_runs = {}
    for k, run in runs.items():
        cursor = weather.index(schedule.shift_years(run["cursor"], k))
        sow = weather.index(schedule.shift_years(step.sow_date, k))
        harvest = weather.index(schedule.shift_years(step.harvest_date, k))
        soil = water.run_fallow(weather, cursor, sow, run["soil"], awc, settings)
        soil, season = water.run_crop(
            weather, sow, harvest, soil, crop, awc, settings, irrigated=irrigated, irrigation_budget=budget
        )
        new_runs[k] = {"soil": soil, "seasons": run["seasons"] + [season], "cursor": step.harvest_date}
    result = {"steps": steps, "runs": new_runs, "rules": rules}
    entry.replay[key] = result
    return result


def _season_hazards(entry: _WeatherEntry, crop: dict, bounds) -> tuple[dict, float, float]:
    """Hazards, combined risk and EcoCrop temperature fit for one crop season, memoised.

    The same crop in the same season window recurs across many rotations.
    """
    key = (crop["id"], bounds)
    cached = entry.hazards.get(key)
    if cached is None:
        found = scoring.hazards(entry.weather, entry.months, crop, bounds)
        temp_suit, _ = scoring.temperature_suitability(entry.weather, crop, bounds)
        cached = (found, scoring.combined_risk(found), temp_suit)
        entry.hazards[key] = cached
    return cached


# ---------------------------------------------------------------- helpers


def _robust(values: list[float]) -> float:
    ordered = sorted(values)
    low = ordered[int(LOW_PERCENTILE * (len(ordered) - 1))]
    mean = sum(ordered) / len(ordered)
    return ROBUST_MEAN_WEIGHT * mean + ROBUST_LOW_WEIGHT * low


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _pct(count: int, total: int) -> str:
    return f"{count} of {total}"


def _criterion(score, basis, summary, source_ids) -> dict:
    return {
        "score": None if score is None else round(_clamp(score), 4),
        "basis": basis,
        "summary": summary,
        "source_ids": list(dict.fromkeys(source_ids)),
    }


def _calendar_entry(step: schedule.Step, crop: dict, cls: str | None, previous: str | None, crops: dict) -> dict:
    reason = f"Regional sowing window for {crop['name'].lower()}"
    reason += " (late window, after the optimal dates)" if step.late else " (optimal dates)"
    if step.idle_days:
        reason += f"; the field waits {step.idle_days} days for this window"
    if previous is not None and cls is not None:
        prev_name = crops[previous]["name"].lower() if previous in crops else previous
        reason += f"; {cls} succession after {prev_name}"
    return {
        "crop_id": step.crop_id,
        "crop_name": crop["name"],
        "sowing_window": {"start": step.sow_start.isoformat(), "end": step.sow_end.isoformat()},
        "harvest_window": {"start": step.harvest_start.isoformat(), "end": step.harvest_end.isoformat()},
        "source_ids": ["ro-agronomy"],
        "reason": reason + ".",
    }


def _unknown(rotation, reason: str, sources: list[dict], gaps: list[str] | None = None) -> dict:
    return {
        "feasibility": "unknown",
        "violations": [],
        "criteria": {},
        "calendar": None,
        "warnings": [],
        "local_checks": [],
        "data_gaps": [reason] + (gaps or []),
        "source_ids": [],
        "sources": sources,
        "scenario_applied": False,
        "fixture": False,
        "rotation": list(rotation),
    }


# ---------------------------------------------------------------- evaluate


def evaluate(rotation: list[str], request: dict, environment: dict, rules: dict) -> dict:
    rotation = list(rotation)
    environment = environment if isinstance(environment, dict) else {}
    crops = {c["id"]: c for c in (rules.get("crops") or []) if isinstance(c, dict) and "id" in c}
    rule_sources = list(rules.get("sources") or [])
    env_sources = _env_sources(environment)
    sources = rule_sources + [s for s in env_sources if s["id"] not in {r["id"] for r in rule_sources}]
    env_ids = [s["id"] for s in env_sources]

    if not crops or "settings" not in rules:
        return _unknown(rotation, "No regional rules are available for this location.", sources, list(rules.get("data_gaps") or []))
    missing = list(dict.fromkeys(c for c in rotation if c not in crops))  # each crop once
    if missing:
        return _unknown(rotation, f"Crops without regional rules: {', '.join(missing)}.", sources)

    settings = rules["settings"]
    available_from = date.fromisoformat(request["available_from"])
    location = request["location"]
    latitude = float(location["latitude"])
    constraints = request.get("constraints") or {}
    irrigated = bool(constraints.get("irrigated"))
    budget = constraints.get("max_irrigation_mm")
    budget = float(budget) if isinstance(budget, (int, float)) else None
    scenario = request.get("scenario") or {}
    temp = float(scenario.get("temp_change_c") or 0.0)
    rain = float(scenario.get("rain_change_pct") or 0.0)
    scenario_on = temp != 0 or rain != 0

    assumptions = [
        "Weather is replayed from past seasons at this point; it is regional context (NASA POWER grid), not a field measurement.",
        "Water: FAO-56 daily soil water balance over a 1.5 m profile carried from crop to crop; crops draw only on their root zone, which deepens from 0.3 m to the crop's rooting depth; no runoff or capillary rise.",
        "Scores compare options with each other; they are not yields, profits or probabilities.",
    ]
    data_gaps: list[str] = []
    local_checks: list[str] = []

    # 1. Calendar and rules.
    steps: list[schedule.Step] = []
    for cid in rotation:
        steps.append(schedule.place_next(crops[cid], steps[-1] if steps else None, available_from, settings))
    checked = schedule.check_rules(rotation, steps, request, rules, crops)
    data_gaps += checked["data_gaps"]
    warnings = list(checked["warnings"])
    previous = checked["previous"]
    chain = [previous] + rotation
    calendar = [
        _calendar_entry(step, crops[step.crop_id], checked["classes"][i], chain[i], crops) for i, step in enumerate(steps)
    ]
    if not request.get("history"):
        data_gaps.append("No crop history: the first crop's fit with the previous crop is not checked.")
        local_checks.append("Confirm which crop was harvested last on this field; the first step depends on it.")
    elif previous is None:
        data_gaps.append("The history does not say which crop was harvested right before the plan.")

    # A check may apply only after certain crops ({"text": ..., "after": [...]}), for
    # example the Fusarium check only when wheat follows maize.
    history_ids = [h["crop_id"] for h in schedule.ordered_history(request)]
    sequence = history_ids + rotation
    offset = len(history_ids)
    for cid in dict.fromkeys(rotation):
        entry = (rules.get("local_checks") or {}).get(cid)
        if isinstance(entry, dict):
            after = set(entry.get("after") or [])
            follows = any(
                sequence[i] == cid and i > 0 and sequence[i - 1] in after
                for i in range(offset, len(sequence))
            )
            if entry.get("text") and (not after or follows):
                local_checks.append(entry["text"])
        elif entry:
            local_checks.append(entry)

    # 2. Soil (structure of the rotation; no weather needed).
    soil_in = _soil_inputs(request, environment, settings)
    soil = scoring.soil_index(steps, checked["classes"], crops, rules, _slope(environment))
    if _slope(environment) is None and not any(
        "srtm" in gap.lower() for gap in environment.get("data_gaps", [])
    ):
        data_gaps.append("No slope data (SRTM): erosion risk is not part of the soil score.")
    comp = soil["components"]
    succession = comp["succession"]
    succession_text = (
        "crop order unknown for the first crop" if succession is None
        else "good crop order" if succession >= 0.8
        else "acceptable crop order" if succession >= 0.5
        else "weak crop order (similar crops follow each other)"
    )
    soil_summary = (
        f"{succession_text[0].upper()}{succession_text[1:]}; {len(soil['families'])} plant families"
        f"{', including a legume that adds nitrogen' if soil['legume'] else ', no legume'}; "
        f"bare soil about {round(soil['bare_days'] / 30)} of {round(soil['total_days'] / 30)} months"
        f"{'; erosion risk from the slope included' if comp.get('erosion') is not None else ''}."
    )
    if soil["bare_days"] > 0.3 * soil["total_days"]:
        local_checks.append("Consider a cover crop in the long gaps between main crops to protect the soil.")

    # 3. Replay over past seasons.
    elevation = _elevation(environment)
    if elevation is None:
        elevation = 0.0
    entry = _weather(environment, latitude, elevation, temp, rain)
    weather = entry.weather
    rainfed = irrigated_runs = None
    shifts: list[int] = []
    if weather is None:
        data_gaps.append("No daily weather from the data service: water, climate and productivity are not computed.")
    else:
        data_gaps += weather.notes
        if _elevation(environment) is None:
            data_gaps.append("Elevation is missing; reference evapotranspiration assumes sea-level air pressure.")
        prefix = tuple(rotation)
        rainfed = _replay(prefix, crops, rules, entry, available_from, soil_in["awc"], False, None)
        if irrigated:
            irrigated_runs = _replay(prefix, crops, rules, entry, available_from, soil_in["awc"], True, budget)
        shifts = sorted(rainfed["runs"])[-settings["max_replay_years"]:]
        if len(shifts) < settings["min_replay_years"]:
            data_gaps.append(
                f"Only {len(shifts)} past season(s) cover the whole plan in the weather record (at least "
                f"{settings['min_replay_years']} needed): water, climate and productivity are not computed."
            )
            shifts = []
        else:
            assumptions.append(
                f"Each plan was replayed over {len(shifts)} past seasons "
                f"between {weather.start.year} and {weather.end.year}; reference evapotranspiration by {weather.et0_method}."
            )

    if soil_in["texture"] is None:
        data_gaps.append("Soil texture unknown: soil water holding uses a loam value (FAO-56 Table 19).")
        local_checks.append("Check the soil texture (or a soil analysis): it sets how much water the soil stores.")
    if soil_in["ph"] is None:
        data_gaps.append("Soil pH unknown: crop fit to soil acidity is not part of productivity.")
    elif soil_in["ph_from"] == "regional":
        data_gaps.append("Soil pH is a regional SoilGrids estimate (250 m), not a field analysis.")

    details = []
    replay_rows = []
    criteria: dict = {}
    water_ids = ["fao56", "fao-wrsi"] + env_ids
    climate_ids = ["ecocrop", "crop-temperature-thresholds"] + env_ids
    criteria["soil"] = _criterion(soil["score"], "estimated", soil_summary, ["ro-agronomy"])

    if shifts:
        n = len(shifts)
        succ_yield = rules["settings"]["successor_yield_factor"]
        season_water, season_climate, season_product = [], [], []
        per_step = [
            {"wrsi": [], "water_y": [], "risk": [], "temp": [], "events": {}, "etc": [], "rain": [], "irr": []}
            for _ in steps
        ]
        for k in shifts:
            seasons = rainfed["runs"][k]["seasons"]
            irr_seasons = irrigated_runs["runs"][k]["seasons"] if irrigated_runs else None
            row = {"season_start_year": steps[0].sow_start.year - k, "steps": []}
            w_vals, c_vals, p_vals = [], [], []
            for i, (step, season) in enumerate(zip(steps, seasons)):
                crop = crops[step.crop_id]
                ky = crop.get("ky", 1.0)
                water_y = _clamp(1 - ky * (1 - season.eta_mm / season.etc_mm)) if season.etc_mm > 0 else 1.0
                found, risk, temp_suit = _season_hazards(entry, crop, season.bounds)
                climate_value = (1 - risk) * (0.5 + 0.5 * temp_suit)
                grow_y = water_y
                if irr_seasons:
                    s2 = irr_seasons[i]
                    grow_y = _clamp(1 - ky * (1 - s2.eta_mm / s2.etc_mm)) if s2.etc_mm > 0 else 1.0
                cls = checked["classes"][i]
                factor = succ_yield.get(cls, 1.0) if cls else 1.0
                factor *= settings["late_sowing_yield_factor"] if step.late else 1.0
                ph_suit = scoring.ph_suitability(soil_in["ph"], crop)
                product = grow_y * (1 - risk) * factor * (ph_suit if ph_suit is not None else 1.0)
                w_vals.append(water_y)
                c_vals.append(climate_value)
                p_vals.append(product)
                acc = per_step[i]
                acc["wrsi"].append(season.wrsi)
                acc["water_y"].append(water_y)
                acc["risk"].append(risk)
                acc["temp"].append(temp_suit)
                acc["etc"].append(season.etc_mm)
                acc["rain"].append(season.rain_mm)
                if irr_seasons:
                    acc["irr"].append(irr_seasons[i].irrigation_mm)
                for name, item in found.items():
                    acc["events"][name] = acc["events"].get(name, 0) + (1 if item["event"] else 0)
                row["steps"].append(
                    {
                        "crop_id": step.crop_id,
                        "wrsi_pct": round(season.wrsi, 1),
                        "water_need_mm": round(season.etc_mm),
                        "water_used_mm": round(season.eta_mm),
                        "season_rain_mm": round(season.rain_mm),
                        "hazards": {name: item["value"] for name, item in found.items()},
                        "climate_risk": round(risk, 3),
                    }
                )
            season_water.append(sum(w_vals) / len(w_vals))
            season_climate.append(sum(c_vals) / len(c_vals))
            season_product.append(sum(p_vals) / len(p_vals))
            row["scores"] = {
                "water": round(season_water[-1], 3),
                "climate": round(season_climate[-1], 3),
                "productivity": round(season_product[-1], 3),
            }
            replay_rows.append(row)

        # Per-step evidence and texts.
        weakest_water, weakest_climate = None, None
        failure = settings["wrsi_failure"]
        for i, step in enumerate(steps):
            crop, acc = crops[step.crop_id], per_step[i]
            fails = sum(1 for w in acc["wrsi"] if w < failure)
            detail = {
                "order": i + 1,
                "crop_id": step.crop_id,
                "crop_name": crop["name"],
                "succession": checked["classes"][i],
                "late_sowing": step.late,
                "water_need_mm": round(sum(acc["etc"]) / n),
                "season_rain_mm": round(sum(acc["rain"]) / n),
                "wrsi_mean_pct": round(sum(acc["wrsi"]) / n, 1),
                "wrsi_worst_pct": round(min(acc["wrsi"]), 1),
                "water_failure_seasons": fails,
                "climate_risk_mean": round(sum(acc["risk"]) / n, 3),
                "temperature_suitability": round(sum(acc["temp"]) / n, 3),
                "hazard_seasons": dict(acc["events"]),
                "seasons": n,
            }
            if acc["irr"]:
                detail["irrigation_mm_mean"] = round(sum(acc["irr"]) / n)
            details.append(detail)
            water_mean = sum(acc["water_y"]) / n
            if weakest_water is None or water_mean < weakest_water[1]:
                weakest_water = (detail, water_mean)
            if weakest_climate is None or detail["climate_risk_mean"] > weakest_climate[0]["climate_risk_mean"]:
                weakest_climate = (detail, detail["climate_risk_mean"])
            # Name the step when the crop occurs more than once in the sequence.
            who = crop["name"] if sum(st.crop_id == step.crop_id for st in steps) == 1 else f"{crop['name']} (crop {i + 1})"
            for name, count in acc["events"].items():
                if count and count / n >= 0.25:
                    label = scoring.HAZARD_LABELS[name].format(**crop["hazards"][name])
                    severity = "high" if count / n >= 0.5 else "medium"
                    warnings.append({"message": f"{who}: {label} in {_pct(count, n)} past seasons.", "severity": severity})
            if fails and fails / n >= 0.25:
                warnings.append(
                    {
                        "message": f"{who}: severe water shortage (less than {failure}% of its need met) in {_pct(fails, n)} past seasons.",
                        "severity": "high" if fails / n >= 0.5 else "medium",
                    }
                )

        mean_wrsi = sum(d["wrsi_mean_pct"] for d in details) / len(details)
        wd = weakest_water[0]
        water_summary = (
            f"In the past {n} seasons, rain and water stored in the soil covered {mean_wrsi:.0f}% of what these crops "
            f"need in an average season. Most exposed: {wd['crop_name'].lower()}, with {wd['wrsi_mean_pct']:.0f}% "
            f"on average and {wd['wrsi_worst_pct']:.0f}% in its driest season."
        )
        if irrigated:
            total_irr = sum(d.get("irrigation_mm_mean", 0) for d in details)
            water_summary += f" With irrigation the plan would use about {total_irr} mm over its three crops."
            assumptions.append("The water score is the rainfed result; irrigation enters the productivity score.")
        cd = weakest_climate[0]
        climate_summary = (
            f"Heat, frost and dry sowing conditions in the past {n} seasons, and how well temperatures suit each crop. "
            f"Most exposed: {cd['crop_name'].lower()}."
        )
        product_summary = (
            "Relative growing potential from water, weather risk, the previous crop and the sowing date"
            + (", plus how well the soil pH suits each crop." if soil_in["ph"] is not None else ".")
            + " Not a yield forecast."
        )
        criteria["water"] = _criterion(_robust(season_water), "derived", water_summary, water_ids)
        criteria["climate"] = _criterion(_robust(season_climate), "derived", climate_summary, climate_ids)
        criteria["productivity"] = _criterion(
            _robust(season_product), "estimated", product_summary, ["fao56", "ecocrop", "ro-agronomy"] + env_ids
        )
        winter = [crops[c]["name"].lower() for c in dict.fromkeys(rotation) if "winterkill" in crops[c].get("hazards", {})]
        if winter:
            data_gaps.append(
                f"Winterkill risk for {', '.join(winter)} ignores snow cover, which protects winter crops; "
                "check winter hardiness locally."
            )
    else:
        for name in ("water", "climate", "productivity"):
            criteria[name] = _criterion(None, "assumed", "Not computed: not enough daily weather data.", [])

    if scenario_on:
        assumptions.append(
            f"Hypothetical scenario applied to every past season: temperature {temp:+.1f} °C, rain {rain:+.0f}%. Not a forecast."
        )

    violations = checked["violations"]
    source_ids = list(dict.fromkeys(["ro-agronomy"] + [i for c in criteria.values() for i in c["source_ids"]]))
    return {
        "feasibility": "infeasible" if violations else "feasible",
        "violations": violations,
        "criteria": criteria,
        "calendar": calendar,
        "warnings": _dedupe_warnings(warnings),
        "local_checks": list(dict.fromkeys(local_checks)),
        "data_gaps": list(dict.fromkeys(data_gaps)),
        "assumptions": assumptions,
        "source_ids": source_ids,
        "sources": sources,
        "scenario_applied": scenario_on and weather is not None,
        "fixture": False,
        "rotation": rotation,
        "region": (rules.get("region") or {}).get("id"),
        "soil_inputs": soil_in,
        "soil_components": soil["components"],
        "details": details,
        "replay": sorted(replay_rows, key=lambda row: row["season_start_year"]),
    }


def _fmt(value) -> str:
    return "unknown" if value is None else f"{value:.2f}"


def _dedupe_warnings(items: list[dict]) -> list[dict]:
    seen, result = set(), []
    for item in items:
        if item["message"] not in seen:
            seen.add(item["message"])
            result.append(item)
    return result
