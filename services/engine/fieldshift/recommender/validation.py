"""Calendar and result checks. These verify temporal consistency, not agronomy."""

from __future__ import annotations

from datetime import date

from .evaluation import CalendarStep


def validate_calendar(
    steps: tuple[CalendarStep, ...], rotation: tuple[str, ...], available_from: date
) -> list[str]:
    """Return every temporal problem of a three-step calendar supplied by P3.

    Rules: the step crops follow the rotation; each window is ordered; sowing ends no
    later than harvest begins; harvest of step i ends strictly before sowing of step i+1
    starts (no overlapping main crops); the first sowing window is still open on
    `available_from`. Year boundaries are handled by real dates (autumn sowing in year Y
    with harvest in Y+1 is valid).
    """
    errors: list[str] = []
    if len(steps) != len(rotation):
        return [f"expected {len(rotation)} steps, got {len(steps)}"]
    for index, step in enumerate(steps):
        n = index + 1
        if step.crop_id != rotation[index]:
            errors.append(f"step {n}: crop {step.crop_id} does not match {rotation[index]}")
        if step.sowing_start > step.sowing_end:
            errors.append(f"step {n}: sowing window ends before it starts")
        if step.harvest_start > step.harvest_end:
            errors.append(f"step {n}: harvest window ends before it starts")
        if step.sowing_end > step.harvest_start:
            errors.append(f"step {n}: sowing window ends after harvest starts")
        if index == 0 and step.sowing_end < available_from:
            errors.append(f"step 1: sowing window closes before available_from {available_from}")
        if index > 0 and steps[index - 1].harvest_end >= step.sowing_start:
            errors.append(f"step {n}: sowing starts before step {index} harvest ends")
    return errors


def history_issues(request: dict, catalog_ids) -> list[str]:
    """Data-quality notes about the crop history that precedes the plan."""
    issues: list[str] = []
    history = request.get("history") or []
    available = date.fromisoformat(request["available_from"])
    for entry in history:
        year = entry.get("harvest_year")
        if year is not None and year > available.year:
            issues.append(
                f"The crop history lists {entry['crop_id']} harvested in {year}, after the year in which "
                f"the field becomes available ({available.year}); please check the crop history."
            )
        if entry["crop_id"] not in catalog_ids:
            issues.append(
                f"The previous crop {entry['crop_id']} is not in the regional rules; "
                "compatibility with it depends on the P3 evaluator."
            )
    return issues


def validate_result_semantics(result: dict) -> list[str]:
    """Python port of `validateResultSemantics` from packages/contracts/src/index.ts."""
    errors: list[str] = []
    plans = result.get("plans", [])
    status = result.get("status")
    if status == "complete" and len(plans) != 3:
        errors.append("A complete result must contain three plans.")
    if status == "limited" and not 1 <= len(plans) <= 2:
        errors.append("A limited result must contain one or two plans.")
    if status == "insufficient_data" and plans:
        errors.append("Insufficient data cannot include plans.")
    ids = {s["id"] for s in result.get("sources", [])}
    signatures = set()
    for plan in plans:
        sig = ">".join(s["crop_id"] for s in plan["steps"])
        if sig in signatures:
            errors.append("Plans must have distinct sequences.")
        signatures.add(sig)
        if any(i not in ids for i in plan["source_ids"]):
            errors.append("Unknown source reference.")
        for i, step in enumerate(plan["steps"]):
            sw, hw = step["sowing_window"], step["harvest_window"]
            if step["order"] != i + 1:
                errors.append("Steps must be ordered 1, 2, 3.")
            if sw["start"] > sw["end"] or hw["start"] > hw["end"] or sw["end"] > hw["start"]:
                errors.append("Invalid crop calendar.")
            if i > 0 and plan["steps"][i - 1]["harvest_window"]["end"] >= sw["start"]:
                errors.append("Crop windows overlap.")
    return errors
