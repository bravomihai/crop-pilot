"""Defensive reader for P3 evaluation dicts (PROPOSED P3–P4 contract, see docs).

`evaluate(rotation, request, environment, rules)` is owned by P3. Until the team agrees
on its output, P4 reads the shape below and treats anything missing or malformed as
UNKNOWN — never as a passing constraint and never as a neutral score:

    {
      "feasibility": "feasible" | "infeasible" | "unknown",
      "violations": ["mandatory constraint that failed", ...],
      "criteria": {
        "water" | "soil" | "climate" | "productivity": {
          "score": float in [0, 1] | null,      # higher = better for that objective
                                                # productivity = relative production
                                                # potential, not a yield/profit forecast
          "basis": "observed" | "derived" | "estimated" | "assumed",
          "summary": "short evidence statement",
          "source_ids": ["..."]
        }
      },
      "calendar": [                              # exactly one entry per rotation crop
        {"crop_id": "...", "crop_name": "...",
         "sowing_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
         "harvest_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
         "source_ids": ["..."], "reason": "..."}
      ],
      "warnings": ["..."] | [{"message": "...", "severity": "low|medium|high"}],
      "data_gaps": ["..."],
      "local_checks": ["what a local agronomist should verify"],
      "assumptions": ["method assumption, e.g. replay period and ET method"],
      "source_ids": ["..."],
      "sources": [{"id": "...", "title": "...", "url": "https://...", "resolution": "..."}],
      "scenario_applied": bool,   # true only if request["scenario"] changed the evaluation
      "fixture": bool             # true marks test/demo evaluators; never real agronomy
    }
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date

from .config import CRITERIA

FEASIBLE, INFEASIBLE, UNKNOWN = "feasible", "infeasible", "unknown"
FEASIBILITY_VALUES = (FEASIBLE, INFEASIBLE, UNKNOWN)
BASIS_VALUES = ("observed", "derived", "estimated", "assumed")
SEVERITIES = ("low", "medium", "high")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SOURCE_KEYS = ("id", "title", "url", "resolution")


@dataclass(frozen=True)
class Criterion:
    name: str
    score: float | None
    basis: str = "assumed"
    summary: str | None = None
    source_ids: tuple[str, ...] = ()

    @property
    def known(self) -> bool:
        return self.score is not None


@dataclass(frozen=True)
class CalendarStep:
    crop_id: str
    crop_name: str | None
    sowing_start: date
    sowing_end: date
    harvest_start: date
    harvest_end: date
    source_ids: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class EvalWarning:
    message: str
    severity: str = "medium"


@dataclass(frozen=True)
class Evaluation:
    rotation: tuple[str, ...]
    feasibility: str
    violations: tuple[str, ...] = ()
    criteria: dict[str, Criterion] = field(default_factory=dict)
    calendar: tuple[CalendarStep, ...] | None = None
    calendar_error: str | None = None
    warnings: tuple[EvalWarning, ...] = ()
    data_gaps: tuple[str, ...] = ()
    local_checks: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    replay: tuple[dict, ...] = ()
    source_ids: tuple[str, ...] = ()
    sources: tuple[dict, ...] = ()
    scenario_applied: bool = False
    fixture: bool = False
    contract_errors: tuple[str, ...] = ()

    def criterion(self, name: str) -> Criterion:
        return self.criteria.get(name) or Criterion(name, None)


def parse_date(value) -> date:
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        raise ValueError(f"not an ISO YYYY-MM-DD date: {value!r}")
    return date.fromisoformat(value)


def _strings(value, errors: list[str], label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{label} must be a list of strings")
        return ()
    return tuple(v for v in value if v.strip())


_REPLAY_STEP_NUMBERS = ("wrsi_pct", "water_need_mm", "water_used_mm", "season_rain_mm", "climate_risk")
_REPLAY_SCORES = ("water", "soil", "climate", "productivity")


def _number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _replay(raw, rotation: tuple[str, ...], errors: list[str]) -> tuple[dict, ...]:
    """Contract-shaped copy of P3's per-season replay (`plan.replay`), oldest first.

    Malformed seasons are dropped with a contract error, never repaired with guesses.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append("replay must be a list")
        return ()
    seasons = []
    for entry in raw:
        try:
            year = entry["season_start_year"]
            if isinstance(year, bool) or not isinstance(year, int):
                raise ValueError("season_start_year must be an integer")
            scores = {}
            for name in _REPLAY_SCORES:
                if name in (entry.get("scores") or {}):
                    value = entry["scores"][name]
                    if value is not None and not (_number(value) and 0 <= value <= 1):
                        raise ValueError(f"score {name} outside [0, 1]")
                    scores[name] = None if value is None else float(value)
            season = {"season_start_year": year, "scores": scores}
            free = entry.get("field_free_from")
            if free is not None:
                if not isinstance(free, str):
                    raise ValueError("field_free_from must be an ISO date")
                date.fromisoformat(free)  # ValueError when malformed
                season["field_free_from"] = free
            steps = entry.get("steps")
            if steps is not None:
                if not isinstance(steps, list) or len(steps) > len(rotation):
                    raise ValueError("steps must be a list no longer than the rotation")
                clean_steps = []
                for index, step in enumerate(steps):
                    if step.get("crop_id") != rotation[index]:
                        raise ValueError("replay step crop does not follow the rotation")
                    clean = {"crop_id": step["crop_id"]}
                    for key in _REPLAY_STEP_NUMBERS:
                        if key in step and (step[key] is None or (_number(step[key]) and step[key] >= 0)):
                            clean[key] = step[key]
                    hazards = step.get("hazards")
                    if isinstance(hazards, dict):
                        clean["hazards"] = {str(k): v for k, v in hazards.items() if _number(v)}
                    clean_steps.append(clean)
                season["steps"] = clean_steps
            seasons.append(season)
        except (KeyError, TypeError, AttributeError, ValueError) as error:
            errors.append(f"replay season dropped: {error}")
    seasons.sort(key=lambda s: s["season_start_year"])
    unique = []
    for season in seasons:
        if not unique or season["season_start_year"] != unique[-1]["season_start_year"]:
            unique.append(season)
    return tuple(unique)


def _score(value, errors: list[str], label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{label} score must be a number in [0, 1]")
        return None
    if not math.isfinite(value) or not 0 <= value <= 1:
        errors.append(f"{label} score {value!r} is outside [0, 1]")
        return None
    return float(value)


def _criteria(raw, errors: list[str]) -> dict[str, Criterion]:
    result = {name: Criterion(name, None) for name in CRITERIA}
    if raw is None:
        return result
    if not isinstance(raw, dict):
        errors.append("criteria must be an object")
        return result
    for name in CRITERIA:
        entry = raw.get(name)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            errors.append(f"criteria.{name} must be an object")
            continue
        basis = entry.get("basis")
        if basis not in BASIS_VALUES:
            if basis is not None:
                errors.append(f"criteria.{name}.basis {basis!r} is not recognised")
            basis = "assumed"  # conservative: unknown provenance is weakest evidence
        summary = entry.get("summary")
        result[name] = Criterion(
            name=name,
            score=_score(entry.get("score"), errors, f"criteria.{name}"),
            basis=basis,
            summary=summary.strip() if isinstance(summary, str) and summary.strip() else None,
            source_ids=_strings(entry.get("source_ids"), errors, f"criteria.{name}.source_ids"),
        )
    return result


def _calendar(raw, rotation: tuple[str, ...]) -> tuple[tuple[CalendarStep, ...] | None, str | None]:
    if raw is None:
        return None, "calendar missing"
    if not isinstance(raw, list) or len(raw) != len(rotation):
        return None, f"calendar must list exactly {len(rotation)} steps"
    steps = []
    for index, entry in enumerate(raw):
        try:
            if not isinstance(entry, dict):
                raise ValueError("step is not an object")
            if entry.get("crop_id") != rotation[index]:
                raise ValueError(
                    f"crop_id {entry.get('crop_id')!r} does not match rotation position {index + 1}"
                )
            sowing, harvest = entry["sowing_window"], entry["harvest_window"]
            name = entry.get("crop_name")
            reason = entry.get("reason")
            ids = entry.get("source_ids") or []
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                raise ValueError("source_ids must be a list of strings")
            steps.append(
                CalendarStep(
                    crop_id=rotation[index],
                    crop_name=name.strip() if isinstance(name, str) and name.strip() else None,
                    sowing_start=parse_date(sowing["start"]),
                    sowing_end=parse_date(sowing["end"]),
                    harvest_start=parse_date(harvest["start"]),
                    harvest_end=parse_date(harvest["end"]),
                    source_ids=tuple(ids),
                    reason=reason.strip() if isinstance(reason, str) and reason.strip() else None,
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            return None, f"calendar step {index + 1}: {error}"
    return tuple(steps), None


def _warnings(raw, errors: list[str]) -> tuple[EvalWarning, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append("warnings must be a list")
        return ()
    result = []
    for entry in raw:
        if isinstance(entry, str) and entry.strip():
            result.append(EvalWarning(entry.strip()))
        elif isinstance(entry, dict) and isinstance(entry.get("message"), str):
            severity = entry.get("severity")
            result.append(
                EvalWarning(entry["message"].strip(), severity if severity in SEVERITIES else "medium")
            )
        else:
            errors.append("unrecognised warning entry")
    return tuple(result)


def valid_source(source) -> dict | None:
    """Return a contract-shaped copy of a source object, or None if it is unusable."""
    if not isinstance(source, dict):
        return None
    if not isinstance(source.get("id"), str) or not source["id"]:
        return None
    if not isinstance(source.get("title"), str) or not source["title"]:
        return None
    clean = {"id": source["id"], "title": source["title"]}
    url = source.get("url")
    if url is not None:
        if not isinstance(url, str) or not re.match(r"^https?://\S+$", url):
            return None
        clean["url"] = url
    resolution = source.get("resolution")
    if isinstance(resolution, str):
        clean["resolution"] = resolution
    return clean


def parse_evaluation(raw, rotation) -> Evaluation:
    rotation = tuple(rotation)
    if not isinstance(raw, dict):
        return Evaluation(rotation, UNKNOWN, contract_errors=("evaluation is not an object",))
    errors: list[str] = []
    feasibility = raw.get("feasibility")
    if feasibility not in FEASIBILITY_VALUES:
        errors.append(f"feasibility {feasibility!r} is not one of {FEASIBILITY_VALUES}")
        feasibility = UNKNOWN
    violations = _strings(raw.get("violations"), errors, "violations")
    if feasibility == FEASIBLE and violations:
        # A reported mandatory violation always wins over a contradictory status.
        errors.append("feasible status contradicted by violations")
        feasibility = INFEASIBLE
    calendar, calendar_error = _calendar(raw.get("calendar"), rotation)
    sources = []
    for source in raw.get("sources") or []:
        clean = valid_source(source)
        if clean is None:
            errors.append("invalid source object dropped")
        else:
            sources.append(clean)
    return Evaluation(
        rotation=rotation,
        feasibility=feasibility,
        violations=violations,
        criteria=_criteria(raw.get("criteria"), errors),
        calendar=calendar,
        calendar_error=calendar_error,
        warnings=_warnings(raw.get("warnings"), errors),
        data_gaps=_strings(raw.get("data_gaps"), errors, "data_gaps"),
        local_checks=_strings(raw.get("local_checks"), errors, "local_checks"),
        assumptions=_strings(raw.get("assumptions"), errors, "assumptions"),
        replay=_replay(raw.get("replay"), rotation, errors),
        source_ids=_strings(raw.get("source_ids"), errors, "source_ids"),
        sources=tuple(sources),
        scenario_applied=raw.get("scenario_applied") is True,
        fixture=raw.get("fixture") is True,
        contract_errors=tuple(errors),
    )
