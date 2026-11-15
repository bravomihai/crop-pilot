"""Rough money estimate per plan, in lei per hectare and year (Romania).

Built from a dated season file (see services/engine/tools/build_economics_ro.py):
- yields: the field's county, INS yields of the last 10 years (20th, 50th, 80th percentile);
- prices: the region's INS farm-gate prices of the last 3 years (lowest, median, highest);
- costs: ICEADR per-hectare budgets (2022-2023 cost level), plus or minus 15 %;
- CAP payments reported for the campaign, converted at the ECB rate of 30 September.

It is an estimate, not a forecast, and it never changes the ranking. Anything missing is
returned as unknown (None), never as zero. Nothing about the farmer is stored.
"""

from __future__ import annotations

import json
import statistics
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "rules" / "economics"
COST_BAND = 0.15
PRICE_YEARS = 3
YIELD_YEARS = 10
MIN_YIELD_YEARS = 5
LEGUMES = {"pea", "soybean"}


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip().lower()


@lru_cache(maxsize=1)
def load_data() -> tuple[dict, list[dict]] | None:
    files = sorted(DATA_DIR.glob("ro_[0-9]*.json"))
    counties = DATA_DIR / "ro_counties.json"
    if not files or not counties.exists():
        return None
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    return data, json.loads(counties.read_text(encoding="utf-8"))["counties"]


def _inside(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def county_at(latitude: float, longitude: float, counties: list[dict]) -> str | None:
    for county in counties:
        if any(_inside(longitude, latitude, ring) for ring in county["rings"]):
            return county["county"]
    return None


def _range(low: float, typical: float, high: float, step: int = 10) -> dict:
    r = lambda v: round(v / step) * step  # noqa: E731
    return {"low": r(low), "typical": r(typical), "high": r(high)}


def _yield_range(data: dict, county: str, crop_id: str, irrigated: bool) -> dict | None:
    series = (data["yields_t_per_ha"].get(county) or {}).get(crop_id) or {}
    values = [v for _, v in sorted(series.items())][-YIELD_YEARS:]
    if len(values) < MIN_YIELD_YEARS:
        return None
    q = statistics.quantiles(values, n=5, method="inclusive")
    low, typical, high = q[0], statistics.median(values), q[3]
    budget = data["costs_lei_per_ha"].get(crop_id)
    if irrigated and budget:
        # County averages are mostly rainfed; ICEADR's irrigated/rainfed yield ratio lifts them.
        factor = budget["yield_irrigated"] / budget["yield_rainfed"]
        low, typical, high = low * factor, typical * factor, high * factor
    return {"low": round(low, 2), "typical": round(typical, 2), "high": round(high, 2)}


def _price_range(data: dict, region: str | None, crop_id: str) -> tuple[dict | None, bool]:
    prices = data["prices_lei_per_t"]
    series = (prices.get(region or "") or {}).get(crop_id)
    national = False
    if not series:
        series, national = (prices.get("TOTAL") or {}).get(crop_id), True
    if not series:
        return None, False
    values = [v for _, v in sorted(series.items())][-PRICE_YEARS:]
    return {"low": min(values), "typical": statistics.median(values), "high": max(values)}, national


def _cost_range(data: dict, crop_id: str, irrigated: bool) -> dict | None:
    budget = data["costs_lei_per_ha"].get(crop_id)
    if not budget:
        return None
    cost = budget["irrigated" if irrigated else "rainfed"]
    return _range(cost * (1 - COST_BAND), cost, cost * (1 + COST_BAND))


def _sum(ranges: list[dict | None]) -> dict | None:
    if not ranges or any(r is None for r in ranges):
        return None
    return {k: sum(r[k] for r in ranges) for k in ("low", "typical", "high")}


def _per_year(total: dict | None, years: float) -> dict | None:
    if total is None:
        return None
    return _range(total["low"] / years, total["typical"] / years, total["high"] / years, step=50)


def plan_economics(plan: dict, request: dict, county: str | None, data: dict) -> dict:
    irrigated = bool((request.get("constraints") or {}).get("irrigated"))
    region = data["county_region"].get(county or "")
    rate = data["eur_ron"]["rate"]
    steps = plan["steps"]
    start = min(date.fromisoformat(s["sowing_window"]["start"]) for s in steps)
    end = max(date.fromisoformat(s["harvest_window"]["end"]) for s in steps)
    years = max((end - start).days / 365.25, 0.5)
    crops, notes, used_national = [], [], False
    for step in steps:
        crop_id, name = step["crop_id"], step["crop_name"]
        yields = _yield_range(data, county, crop_id, irrigated) if county else None
        price, national = _price_range(data, region, crop_id)
        used_national |= national
        income = None
        if yields and price:
            income = _range(yields["low"] * price["low"], yields["typical"] * price["typical"],
                            yields["high"] * price["high"])
        costs = _cost_range(data, crop_id, irrigated)
        if price is None:
            notes.append(f"{name}: no official recent price series, so its income is unknown.")
        if costs is None:
            notes.append(f"{name}: no published cost budget, so its costs are unknown.")
        if yields is None:
            notes.append(f"{name}: not enough county yield statistics, so its income is unknown.")
        crops.append({"crop_id": crop_id, "crop_name": name, "yield_t_per_ha": yields,
                      "price_lei_per_t": price, "income": income, "costs": costs})
    if used_national:
        notes.append("Some prices are national averages: no regional price for this region.")

    income_total = _sum([c["income"] for c in crops])
    costs_total = _sum([c["costs"] for c in crops])
    ids = [s["crop_id"] for s in steps]

    payments, sure, possible = [], 0.0, 0.0
    for payment in data["payments"]:
        eur = payment.get("eur_per_ha")
        kind = payment["applies"]
        if kind == "all":
            lei = eur * rate
            sure += lei
            payments.append(_payment(payment, lei, "always"))
        elif kind == "crop":
            count = sum(1 for c in ids if c in payment.get("crops", []))
            if count:
                lei = eur * rate * count / years
                sure += lei
                payments.append(_payment(payment, lei, "always"))
        elif kind == "eco_scheme":
            lei = eur * rate
            possible += lei
            helps = []
            if LEGUMES & set(ids):
                helps.append("grows a nitrogen-fixing legume")
            if len(set(ids)) >= 3:
                helps.append("grows 3 different crops")
            entry = _payment(payment, lei, "if_eligible")
            if helps:
                entry["condition"] = (f"This plan {' and '.join(helps)}, which helps meet the eco-scheme's optional "
                                      "requirements, if the rest of your farm also meets them. " + entry["condition"])
            payments.append(entry)
        else:
            payments.append(_payment(payment, None, "not_included"))
    subsidies = _range(sure, sure, sure + possible)

    warnings = []
    for before, after in zip(steps, steps[1:]):
        if before["crop_id"] == after["crop_id"]:
            warnings.append(
                f"{after['crop_name']} follows {before['crop_name'].lower()} on the same field. The EU crop-rotation "
                "standard (GAEC 7) asks for a change of crop each year, so this may reduce your payments; check with APIA."
            )

    income_year = _per_year(income_total, years)
    costs_year = _per_year(costs_total, years)
    margin = None
    if income_year and costs_year:
        margin = {
            "low": income_year["low"] - costs_year["high"] + subsidies["low"],
            "typical": income_year["typical"] - costs_year["typical"] + subsidies["typical"],
            "high": income_year["high"] - costs_year["low"] + subsidies["high"],
        }
    return {
        "currency": "RON",
        "covered_years": round(years, 2),
        "county": _county_label(county),
        "per_year": {"income": income_year, "costs": costs_year, "subsidies": subsidies, "margin": margin},
        "crops": crops,
        "payments": payments,
        "warnings": warnings,
        "notes": list(dict.fromkeys(notes)),
        "source_ids": [s["id"] for s in data["sources"]],
    }


def _payment(payment: dict, lei: float | None, included: str) -> dict:
    return {
        "id": payment["id"],
        "label": payment["label"],
        "lei_per_ha_year": None if lei is None else round(lei / 10) * 10,
        "included": included,
        "condition": payment["condition"],
    }


def _county_label(county: str | None) -> str | None:
    return None if county is None else " ".join(w.capitalize() for w in county.split())


ASSUMPTIONS = [
    "Money per hectare and year is an estimate, not a forecast, and it does not change the ranking: county "
    "yields (INS, last 10 years) times regional farm-gate prices (INS, last 3 years), minus ICEADR cost "
    "budgets, plus CAP payments.",
    "Crop costs are ICEADR budgets at the 2022-2023 cost level; input prices have risen since, so real costs "
    "are probably higher and margins lower. Use your own costs where you know them.",
    "CAP payment rates are those reported for the current campaign and are converted at the ECB rate of "
    "30 September; check the amounts and your eligibility with APIA.",
]


def add_economics(result: dict, request: dict) -> None:
    """Attach `economics` to every plan and the baseline of a computed result (in place)."""
    loaded = load_data()
    if loaded is None:
        result["data_gaps"].append("Money estimate unavailable: the season data file is missing.")
        return
    data, counties = loaded
    location = result["location"]
    county = county_at(location["latitude"], location["longitude"], counties)
    if county is None:
        result["data_gaps"].append("Money estimate unavailable: the field is outside the Romanian county data.")
        return
    targets = list(result["plans"]) + ([result["baseline"]] if result.get("baseline") else [])
    if not targets:
        return
    for plan in targets:
        plan["economics"] = plan_economics(plan, request, county, data)
    listed = {s["id"] for s in result["sources"]}
    result["sources"] = result["sources"] + [s for s in data["sources"] if s["id"] not in listed]
    result["assumptions"] = list(dict.fromkeys(result["assumptions"] + ASSUMPTIONS))
