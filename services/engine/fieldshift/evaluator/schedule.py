"""Place a rotation in time and check it against the regional rotation rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Step:
    crop_id: str
    sow_start: date
    sow_end: date
    harvest_start: date
    harvest_end: date
    late: bool  # sown after the optimal window
    idle_days: int  # days the field waits between becoming free and the sowing window

    @property
    def sow_date(self) -> date:
        return self.sow_start + (self.sow_end - self.sow_start) / 2

    @property
    def harvest_date(self) -> date:
        return self.harvest_start + (self.harvest_end - self.harvest_start) / 2


def month_day(year: int, text: str) -> date:
    month, day = (int(part) for part in text.split("-"))
    return date(year, month, day)


def shift_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def place_step(crop: dict, free_from: date, min_window_days: int) -> Step:
    """First sowing window of `crop` that is still open on or after `free_from`."""
    sowing, harvest = crop["sowing"], crop["harvest"]
    for year in range(free_from.year, free_from.year + 3):
        start = max(free_from, month_day(year, sowing["start"]))
        optimal_end, latest = month_day(year, sowing["optimal_end"]), month_day(year, sowing["latest"])
        if (optimal_end - start).days + 1 >= min_window_days:
            end, late = optimal_end, False
        elif (latest - start).days + 1 >= min_window_days:
            end, late = latest, True
        else:
            continue
        harvest_year = year + harvest["year_offset"]
        return Step(
            crop["id"],
            start,
            end,
            month_day(harvest_year, harvest["start"]),
            month_day(harvest_year, harvest["end"]),
            late,
            (start - free_from).days,
        )
    raise ValueError(f"no sowing window found for {crop['id']}")  # unreachable with valid rules


def place_next(crop: dict, previous: Step | None, available_from: date, settings: dict) -> Step:
    free_from = (
        available_from if previous is None else previous.harvest_end + timedelta(days=settings["turnaround_days"])
    )
    return place_step(crop, free_from, settings["min_sowing_window_days"])


def season_before(crop: dict, day: date) -> tuple[date, date] | None:
    """Typical (sowing, harvest) dates of the last season of `crop` that ended before `day`."""
    sowing, harvest = crop["sowing"], crop["harvest"]
    for year in (day.year, day.year - 1, day.year - 2):
        h_start, h_end = month_day(year, harvest["start"]), month_day(year, harvest["end"])
        harvest_mid = h_start + (h_end - h_start) / 2
        if harvest_mid <= day:
            sow_year = year - harvest["year_offset"]
            s_start, s_end = month_day(sow_year, sowing["start"]), month_day(sow_year, sowing["optimal_end"])
            return s_start + (s_end - s_start) / 2, harvest_mid
    return None


def ordered_history(request: dict) -> list[dict]:
    """History oldest → newest. Entries with a harvest year are sorted by it."""
    history = [h for h in (request.get("history") or []) if isinstance(h, dict) and h.get("crop_id")]
    if history and all(isinstance(h.get("harvest_year"), int) for h in history):
        history = sorted(history, key=lambda h: h["harvest_year"])
    return history


def previous_crop(request: dict, first_sowing_year: int) -> str | None:
    """The crop grown right before the plan, if the history says so."""
    history = ordered_history(request)
    if not history:
        return None
    last = history[-1]
    year = last.get("harvest_year")
    if isinstance(year, int) and first_sowing_year - year > 1:
        return None  # an older entry is not the immediate predecessor
    return last["crop_id"]


def successor_reason(rules: dict, previous: str, following: str) -> str | None:
    for reason in (rules.get("successor_reasons") or {}).values():
        if [previous, following] in reason.get("pairs", []):
            return reason["text"]
    return None


def successor_class(rules: dict, previous: str | None, following: str) -> str | None:
    if previous is None:
        return None
    return (rules.get("successor") or {}).get(previous, {}).get(following)


def check_rules(rotation: list[str], steps: list[Step], request: dict, rules: dict, crops: dict) -> dict:
    """Violations (hard rules), warnings and notes for a placed rotation."""
    settings = rules["settings"]
    violations: list[str] = []
    warnings: list[dict] = []
    gaps: list[str] = []
    names = {cid: crops[cid]["name"] for cid in rotation}

    excluded = set((request.get("constraints") or {}).get("excluded_crops") or [])
    for cid in dict.fromkeys(rotation):
        if cid in excluded:
            violations.append(f"{names[cid]} is on the farmer's list of excluded crops.")

    history = ordered_history(request)
    before = previous_crop(request, steps[0].sow_start.year)
    if before is not None and before not in crops and before not in (rules.get("successor") or {}):
        gaps.append(f"The previous crop ({before}) is not in the regional rules; its effect on the first crop is not checked.")
        before = None

    # Succession, pair by pair (the crop grown before the plan counts for the first step).
    chain = [before] + list(rotation)
    classes: list[str | None] = []
    for index in range(1, len(chain)):
        prev, nxt = chain[index - 1], chain[index]
        cls = successor_class(rules, prev, nxt)
        classes.append(cls)
        if prev is None or cls is None:
            continue
        prev_name = crops[prev]["name"] if prev in crops else prev
        reason = successor_reason(rules, prev, nxt)
        text = f"{names[nxt]} after {prev_name.lower()}" + (f": {reason}" if reason else "")
        if cls == "forbidden":
            violations.append(f"{text} (not recommended in rotation guidance).")
        elif cls == "poor":
            warnings.append({"message": f"Weak succession: {text}.", "severity": "medium"})

    # Too many consecutive seasons of one crop (history tail included).
    tail = [h["crop_id"] for h in history]
    sequence = tail + list(rotation)
    run = 1
    for index in range(1, len(sequence)):
        run = run + 1 if sequence[index] == sequence[index - 1] else 1
        cid = sequence[index]
        if index >= len(tail) and cid in crops and run > crops[cid].get("max_consecutive", 1):
            message = f"{names[cid]} would be grown {run} times in a row (maximum {crops[cid].get('max_consecutive', 1)})."
            if message not in violations and successor_class(rules, cid, cid) != "forbidden":
                violations.append(message)

    # Return interval between two crops of the same species.
    harvests: dict[str, list[int]] = {}
    undated = False
    for entry in history:
        if isinstance(entry.get("harvest_year"), int):
            harvests.setdefault(entry["crop_id"], []).append(entry["harvest_year"])
        else:
            undated = True
    planned = {cid: [] for cid in rotation}
    for step in steps:
        planned[step.crop_id].append(step.harvest_end.year)
    for cid, years in planned.items():
        interval = crops[cid].get("return_years")
        if not interval:
            continue
        timeline = sorted(harvests.get(cid, []) + years)
        for earlier, later in zip(timeline, timeline[1:]):
            if later in years and 0 < later - earlier < interval:
                message = (
                    f"{names[cid]} would return after {later - earlier} year(s) "
                    f"(harvests {earlier} and {later}); the minimum interval is {interval} years."
                )
                if later - earlier > 1 or successor_class(rules, cid, cid) != "forbidden":
                    violations.append(message)
    if undated and any(crops[cid].get("return_years") for cid in rotation):
        gaps.append("Some history entries have no harvest year; return intervals are only checked for dated entries.")

    # Timing notes.
    for index, step in enumerate(steps):
        name = names[step.crop_id]
        if step.late:
            warnings.append(
                {
                    "message": f"{name} would be sown after its optimal window (from {step.sow_start.isoformat()}); expect lower yield potential.",
                    "severity": "medium",
                }
            )
        if index > 0:
            gap = (step.sow_start - steps[index - 1].harvest_end).days
            prev_name = names[steps[index - 1].crop_id].lower()
            if step.idle_days == 0 and gap < settings["tight_turnaround_days"]:
                warnings.append(
                    {
                        "message": f"Tight turnaround: {gap} days between the {prev_name} harvest and sowing {name.lower()}; an early-maturing variety and fast residue management are needed.",
                        "severity": "medium",
                    }
                )
            if gap > settings["long_idle_days"]:
                warnings.append(
                    {
                        "message": f"The field stays without a main crop for about {round(gap / 30)} months between {prev_name} and {name.lower()}; consider a cover crop.",
                        "severity": "medium",
                    }
                )
    return {"violations": list(dict.fromkeys(violations)), "warnings": warnings, "data_gaps": gaps, "classes": classes, "previous": before}
