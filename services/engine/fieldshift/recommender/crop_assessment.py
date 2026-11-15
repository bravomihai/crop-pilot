"""Screen individual crops independently of three-crop rotation rankings."""

import math

from ..evaluator.scoring import ph_suitability


def _windows(outcome: dict) -> dict:
    calendar = outcome.get("calendar") or []
    if not calendar:
        return {}
    first = calendar[0]
    return {
        key: first[key]
        for key in ("sowing_window", "harvest_window")
        if first.get(key) is not None
    }


def assess_crops(request: dict, environment: dict, rules: dict, evaluate) -> dict:
    selected_ids = list(dict.fromkeys(request.get("assessment_crops") or []))
    crops = {crop["id"]: crop for crop in rules.get("crops", [])}
    excluded = set((request.get("constraints") or {}).get("excluded_crops") or [])
    evaluated = {}
    for crop_id, crop in crops.items():
        if crop_id in excluded and crop_id not in selected_ids:
            continue
        outcome = evaluate([crop_id], request, environment, rules)
        value = (outcome.get("criteria", {}).get("productivity") or {}).get("score")
        score = (
            float(value)
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 1
            else None
        )
        ph = (outcome.get("soil_inputs") or {}).get("ph")
        ph_fit = ph_suitability(ph, crop) if ph is not None else None
        violations = outcome.get("violations") or []
        evaluated[crop_id] = (crop, outcome, score, ph_fit, violations)

    alternatives = sorted(
        (
            {
                "crop_id": crop_id,
                "crop_name": crop["name"],
                "score": score,
                **_windows(outcome),
            }
            for crop_id, (crop, outcome, score, ph_fit, violations) in evaluated.items()
            if crop_id not in selected_ids
            and crop_id not in excluded
            and not violations
            and outcome.get("feasibility") == "feasible"
            and ph_fit != 0
            and score is not None
        ),
        key=lambda item: (-item["score"], item["crop_name"]),
    )[:3]
    selected = []
    for crop_id in selected_ids:
        if crop_id not in evaluated:
            selected.append({
                "crop_id": crop_id,
                "crop_name": crop_id.replace("_", " "),
                "status": "uncertain",
                "score": None,
                "message": "No crop rules are available for this crop.",
            })
            continue
        crop, outcome, score, ph_fit, violations = evaluated[crop_id]
        comparable_scores = [
            other_score
            for other_id, (_, other_outcome, other_score, other_ph_fit, other_violations) in evaluated.items()
            if other_id != crop_id
            and other_id not in excluded
            and other_outcome.get("feasibility") == "feasible"
            and not other_violations
            and other_ph_fit != 0
            and other_score is not None
        ]
        has_higher = score is not None and any(other > score for other in comparable_scores)
        if violations:
            status, message = "not_recommended", " ".join(violations)
        elif ph_fit == 0:
            status = "not_recommended"
            message = (
                "The available soil pH is outside this crop's provisional range. "
                "Confirm it with a local soil analysis before planting."
            )
        elif score is None or outcome.get("feasibility") != "feasible":
            status, message = "uncertain", "Not enough evidence is available to compare this crop."
        elif ph_fit is None:
            status = "uncertain"
            message = (
                "Soil pH is unknown, so soil suitability cannot be confirmed. "
                "The score compares available weather and water evidence only."
            )
        elif not (outcome.get("soil_inputs") or {}).get("texture"):
            status = "uncertain"
            message = (
                "Soil texture is unknown, so the water estimate uses an assumed value. "
                "Verify soil conditions before planting."
            )
        elif (environment.get("land_cover") or {}).get("status") == "uncertain":
            status = "uncertain"
            message = "Land cover is uncertain; verify the field is cultivable before planting."
        else:
            status = "assessed"
            if has_higher:
                message = (
                    "The available pH is within the provisional crop range. Another crop "
                    "has higher estimated growing potential under these assumptions."
                )
            elif comparable_scores:
                message = (
                    "The available pH is within the provisional crop range. No alternative "
                    "scored higher under these assumptions; other conditions may still limit it."
                )
            else:
                message = (
                    "The available pH is within the provisional crop range, but no other "
                    "crops could be compared; other conditions may still limit it."
                )
        if status == "uncertain" and has_higher:
            message += " Other crops scored higher on the available evidence, but their suitability also needs checking."
        selected.append({
            "crop_id": crop_id,
            "crop_name": crop["name"],
            "status": status,
            "score": score,
            "message": message,
            **_windows(outcome),
        })
    return {
        "selected": selected,
        "alternatives": alternatives,
        "disclaimer": (
            "Provisional relative growing-potential estimates, not yields or proof of soil "
            "suitability. They use regional historical weather, water and available pH; "
            "they do not rank by the rotation priorities. Check soil, land use and crop "
            "rules locally. Crops may have different next sowing windows. "
            "Hypothetical scenarios are not forecasts."
        ),
    }
