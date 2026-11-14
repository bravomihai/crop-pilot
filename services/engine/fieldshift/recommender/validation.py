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
        if catalog_ids and entry["crop_id"] not in catalog_ids:  # no rules at all: reported elsewhere
            issues.append(
                f"The previous crop {entry['crop_id']} is not in the regional rules; "
                "its fit with the first planned crop is not checked."
            )
    return issues


def validate_result_semantics(result: dict) -> list[str]:
    """Python port of `validateResultSemantics` from packages/contracts/src/index.ts.

    Keep in sync with the Zod source, including the optional `baseline` and `violations`
    rules. Like the TypeScript version, baseline calendars are not checked here.
    """
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
        if plan.get("violations"):
            errors.append("Recommended plans cannot break agronomic rules.")
    baseline = result.get("baseline")
    if baseline:
        if any(i not in ids for i in baseline["source_ids"]):
            errors.append("Unknown source reference in baseline.")
        for i, step in enumerate(baseline["steps"]):
            if step["order"] != i + 1:
                errors.append("Baseline steps must be ordered 1, 2, 3.")
    for plan in list(result["plans"]) + ([baseline] if baseline else []):
        replay = plan.get("replay") or []
        years = [season["season_start_year"] for season in replay]
        if any(later <= earlier for earlier, later in zip(years, years[1:])):
            errors.append("Replay seasons must be in increasing year order.")
        crops = [step["crop_id"] for step in plan["steps"]]
        if any(s["crop_id"] != crops[i] for season in replay for i, s in enumerate(season.get("steps") or [])):
            errors.append("Replay steps must follow the plan's crops.")
    climate = result.get("climate_context")
    if climate:
        if any(i not in ids for i in climate["source_ids"]):
            errors.append("Unknown source reference in climate context.")
        years = [y["year"] for y in climate["years"]]
        if any(later <= earlier for earlier, later in zip(years, years[1:])):
            errors.append("Climate years must be in increasing order.")
        period = climate["period"]
        if period["start_year"] > period["end_year"] or any(
            y < period["start_year"] or y > period["end_year"] for y in years
        ):
            errors.append("Climate years must lie inside the climate period.")
    return errors


def ordered_history(history: list[dict]) -> list[dict]:
    """History oldest → newest.

    If every entry has `harvest_year`, entries are sorted by it (stable, so same-year
    entries keep their list order). Otherwise the list order given by the farmer is used,
    because mixing dated and undated entries would require guessing.
    """
    history = list(history or [])
    if history and all(e.get("harvest_year") is not None for e in history):
        return sorted(history, key=lambda e: e["harvest_year"])
    return history
