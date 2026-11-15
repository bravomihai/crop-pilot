"""Rough money estimate per plan, in lei per hectare and year (Romania).

Built from a dated season file (see services/engine/tools/build_economics_ro.py):
- yields: the field's county, INS yields of commercial farms over the last 10 years
  (all farms when commercial figures are too thin); the range is the 20th, 50th and 80th
  percentile, i.e. bad, typical and good years;
- crop order: the regional rules rate each previous crop -> crop pair (good, ok, poor); the
  rating adjusts the yield, and a legume before a non-legume saves nitrogen fertiliser
  (kg N left by the legume x the official nitrogen price);
- prices: the region's INS farm-gate prices, median of the last 3 years (or the farmer's own);
- costs: ICEADR per-hectare budgets (2022-2023), indexed to the latest official fertiliser and
  diesel prices (or the farmer's own);
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
PRICE_YEARS = 3
# A crop without a price in the last PRICE_YEARS data years may use an older one, up to this
# many years back, and the plan says how old it is. Older prices count as unknown.
MAX_PRICE_AGE = 5
# Warn when the yields used are below this share of the yield a cost budget is written for.
MISMATCH_SHARE = 0.7
YIELD_YEARS = 10
MIN_YIELD_YEARS = 5
LEGUMES = {"pea", "soybean", "dry_beans"}
# County averages mix fields after every kind of previous crop; they are taken as the "ok" level.
AVERAGE_CLASS = "ok"


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


def _round(value: float, step: int = 10) -> int:
    return round(value / step) * step


def _range(low: float, typical: float, high: float, step: int = 10) -> dict:
    return {"low": _round(low, step), "typical": _round(typical, step), "high": _round(high, step)}


def _legumes(rules: dict, data: dict) -> set[str]:
    """Legumes from the regional rules and from the nitrogen-credit table."""
    from_rules = {c["id"] for c in rules.get("crops") or [] if c.get("legume")}
    return LEGUMES | from_rules | set(data.get("nitrogen_credit_kg_per_ha") or {})


def _yields(data: dict, county: str, crop_id: str) -> tuple[list[float], str] | None:
    for key, basis in (("yields_commercial_t_per_ha", "commercial_farms"), ("yields_t_per_ha", "all_farms")):
        series = ((data.get(key) or {}).get(county) or {}).get(crop_id) or {}
        values = [v for _, v in sorted(series.items())][-YIELD_YEARS:]
        if len(values) >= MIN_YIELD_YEARS:
            return values, basis
    series = (data.get("yields_national_t_per_ha") or {}).get(crop_id) or {}
    values = [v for _, v in sorted(series.items())][-YIELD_YEARS:]
    if len(values) >= MIN_YIELD_YEARS:
        return values, "national"
    return None


def _latest_price_year(data: dict) -> int:
    years = [int(y) for region in data["prices_lei_per_t"].values() for series in region.values() for y in series]
    return max(years) if years else 0


def _price(data: dict, region: str | None, crop_id: str, own: dict) -> tuple[dict | None, str | None, int | None]:
    """Price range, its basis, and the latest year used (None for the farmer's own price)."""
    if isinstance(own.get(crop_id), (int, float)) and own[crop_id] > 0:
        value = float(own[crop_id])
        return {"low": value, "typical": value, "high": value}, "farmer", None
    prices = data["prices_lei_per_t"]
    latest = _latest_price_year(data)
    for oldest in (latest - PRICE_YEARS + 1, latest - MAX_PRICE_AGE + 1):
        for basis, series in (("regional", (prices.get(region or "") or {}).get(crop_id)),
                              ("national", (prices.get("TOTAL") or {}).get(crop_id))):
            recent = sorted((int(y), v) for y, v in (series or {}).items() if int(y) >= oldest)[-PRICE_YEARS:]
            if recent:
                values = [v for _, v in recent]
                return ({"low": min(values), "typical": statistics.median(values), "high": max(values)},
                        basis, recent[-1][0])
    return None, None, None


def _base_cost(data: dict, crop_id: str, irrigated: bool, own: dict) -> tuple[float | None, str | None, str | None]:
    """Cost per hectare, its basis, and the crop whose budget stands in for this one (if any)."""
    if isinstance(own.get(crop_id), (int, float)) and own[crop_id] > 0:
        return float(own[crop_id]), "farmer", None
    budget = data["costs_lei_per_ha"].get(crop_id)
    if not budget:
        return None, None, None
    factor = (data.get("cost_index") or {}).get("factor", 1.0)
    proxy = budget.get("proxy_of")
    return budget["irrigated" if irrigated else "rainfed"] * factor, "proxy" if proxy else "iceadr", proxy


def _previous_effect(rules: dict, data: dict, previous: str | None, crop_id: str, legumes: set[str]) -> dict:
    """Yield factor from the previous-crop rating, and kg N left by a previous legume."""
    effect = {"previous": previous, "rating": None, "yield_factor": 1.0, "nitrogen_kg": None}
    if previous is None:
        return effect
    rating = ((rules.get("successor") or {}).get(previous) or {}).get(crop_id)
    factors = (rules.get("settings") or {}).get("successor_yield_factor") or {}
    if rating in factors and AVERAGE_CLASS in factors:
        effect["rating"] = rating
        effect["yield_factor"] = factors[rating] / factors[AVERAGE_CLASS]
    credit = (data.get("nitrogen_credit_kg_per_ha") or {}).get(previous)
    if credit and crop_id not in legumes:
        effect["nitrogen_kg"] = credit
    return effect


def _sum(ranges: list[dict | None]) -> dict | None:
    if not ranges or any(r is None for r in ranges):
        return None
    return {k: sum(r[k] for r in ranges) for k in ("low", "typical", "high")}


def _per_year(total: dict | None, years: float) -> dict | None:
    if total is None:
        return None
    return _range(total["low"] / years, total["typical"] / years, total["high"] / years, step=50)


def _previous_crop(request: dict) -> str | None:
    history = request.get("history") or []
    dated = [h for h in history if h.get("harvest_year")]
    last = max(dated, key=lambda h: h["harvest_year"]) if dated else (history[-1] if history else None)
    return last["crop_id"] if last else None


def plan_economics(plan: dict, request: dict, county: str | None, data: dict, rules: dict | None = None) -> dict:
    rules = rules or {}
    irrigated = bool((request.get("constraints") or {}).get("irrigated"))
    own = request.get("money_inputs") or {}
    own_prices, own_costs = own.get("prices_lei_per_t") or {}, own.get("costs_lei_per_ha") or {}
    region = data["county_region"].get(county or "")
    rate = data["eur_ron"]["rate"]
    n_price = (data.get("nitrogen_price_lei_per_kg") or {}).get("value")
    names = {c["id"]: c["name"] for c in rules.get("crops") or []}
    steps = plan["steps"]
    start = min(date.fromisoformat(s["sowing_window"]["start"]) for s in steps)
    end = max(date.fromisoformat(s["harvest_window"]["end"]) for s in steps)
    years = max((end - start).days / 365.25, 0.5)

    crops, notes, order_effects = [], [], []
    legumes = _legumes(rules, data)
    previous = _previous_crop(request)
    for step in steps:
        crop_id, name = step["crop_id"], step["crop_name"]
        effect = _previous_effect(rules, data, previous, crop_id, legumes)
        found = _yields(data, county, crop_id) if county else None
        yields, yield_basis = None, None
        if found:
            values, yield_basis = found
            q = statistics.quantiles(values, n=5, method="inclusive")
            low, typical, high = q[0], statistics.median(values), q[3]
            budget = data["costs_lei_per_ha"].get(crop_id)
            if irrigated and budget:
                # County yields are mostly rainfed; ICEADR's irrigated/rainfed yield ratio lifts them.
                ratio = budget["yield_irrigated"] / budget["yield_rainfed"]
                low, typical, high = low * ratio, typical * ratio, high * ratio
            f = effect["yield_factor"]
            yields = {"low": round(low * f, 2), "typical": round(typical * f, 2), "high": round(high * f, 2)}
        price, price_basis, price_year = _price(data, region, crop_id, own_prices)
        base_cost, cost_basis, cost_proxy = _base_cost(data, crop_id, irrigated, own_costs)

        income = None
        if yields and price:
            # Bad, typical and good years at the typical price: the range shows weather risk,
            # not every bad case at once. Price swings are listed separately.
            income = _range(yields["low"] * price["typical"], yields["typical"] * price["typical"],
                            yields["high"] * price["typical"])
        saving = None
        if effect["nitrogen_kg"] and n_price:
            kg = effect["nitrogen_kg"]
            saving = _range(kg[0] * n_price, kg[1] * n_price, kg[2] * n_price)
        costs = None
        if base_cost is not None:
            s = saving or {"low": 0, "typical": 0, "high": 0}
            # A bigger nitrogen saving means a lower cost: low cost pairs with the high saving.
            costs = _range(base_cost - s["high"], base_cost - s["typical"], base_cost - s["low"])

        order_value = None
        if price and found and (effect["yield_factor"] != 1.0 or saving):
            unadjusted = yields["typical"] / effect["yield_factor"]
            extra_income = (yields["typical"] - unadjusted) * price["typical"]
            order_value = _round(extra_income + (saving["typical"] if saving else 0))
            order_effects.append(order_value)

        if price is None:
            notes.append(f"{name}: no official recent price series. Add the price you get to complete the estimate.")
        elif price_year is not None and price_year <= _latest_price_year(data) - PRICE_YEARS:
            notes.append(f"{name}: the latest official price is from {price_year}; prices may have changed since. "
                         "Add the price you get for a better estimate.")
        elif price_basis == "national":
            notes.append(f"{name}: national average price; no regional price for this region.")
        if base_cost is None:
            notes.append(f"{name}: no published cost budget. Add your cost per hectare to complete the estimate.")
        if found is None:
            notes.append(f"{name}: not enough county yield statistics, so its income is unknown.")
        elif yield_basis == "all_farms":
            notes.append(f"{name}: commercial-farm yields are too thin in this county; all farms are used.")
        elif yield_basis == "national":
            notes.append(f"{name}: no county yield statistics; the national average yield is used.")
        budget = data["costs_lei_per_ha"].get(crop_id) or {}
        if yields and cost_basis == "iceadr" and yield_basis != "commercial_farms":
            planned = budget["yield_irrigated" if irrigated else "yield_rainfed"] / 1000
            if yields["typical"] < MISMATCH_SHARE * planned:
                notes.append(
                    f"{name}: the yields used ({yields['typical']:.1f} t/ha, mostly small farms) are far below the "
                    f"{planned:.1f} t/ha the cost budget is written for, so the margin is probably too low for a "
                    "commercial farm. Add your own price and cost for a better estimate."
                )
        if cost_basis == "proxy":
            stand_in = names.get(cost_proxy, cost_proxy.replace("_", " ")).lower()
            notes.append(f"{name}: no published cost budget; the {stand_in} budget stands in for it. "
                         "Add your own cost for a better estimate.")

        crops.append({
            "crop_id": crop_id,
            "crop_name": name,
            "previous_crop": names.get(previous, previous) if previous else None,
            "previous_rating": effect["rating"],
            "yield_t_per_ha": yields,
            "yield_basis": yield_basis,
            "price_lei_per_t": price,
            "price_basis": price_basis,
            "income": income,
            "costs": costs,
            "cost_basis": cost_basis,
            "nitrogen_saving": saving,
            "crop_order_effect": order_value,
        })
        previous = crop_id

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
        elif kind == "crop_contract":
            count = sum(1 for c in ids if c in payment.get("crops", []))
            if count:
                lei = eur * rate * count / years
                possible += lei
                payments.append(_payment(payment, lei, "if_eligible"))
        elif kind == "eco_scheme":
            lei = eur * rate
            possible += lei
            helps = []
            if legumes & set(ids):
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
    order_year = _round(sum(order_effects) / years, 50) if order_effects else None
    return {
        "currency": "RON",
        "covered_years": round(years, 2),
        "county": _county_label(county),
        "per_year": {
            "income": income_year,
            "costs": costs_year,
            "subsidies": subsidies,
            "margin": margin,
            "crop_order_effect": order_year,
        },
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
    "Money per hectare and year is an estimate, not a forecast, and it does not change the ranking: "
    "commercial-farm yields in the county (INS, last 10 years) at the region's median farm-gate price "
    "(INS, last 3 years), minus ICEADR cost budgets indexed to official input prices, plus CAP payments. "
    "The range shows bad, typical and good years.",
    "Crop order counts: a good previous crop raises the expected yield and a poor one lowers it (regional "
    "rules), and after a legume (pea, soybean, dry beans) the next crop needs about 20-50 kg less nitrogen "
    "per hectare.",
    "Where a crop has no county statistics or no published cost budget, the national average yield or the "
    "budget of the closest crop is used, and the plan says so.",
    "CAP payment rates are those reported for the current campaign and are converted at the ECB rate of "
    "30 September; check the amounts and your eligibility with APIA.",
]


def add_economics(result: dict, request: dict, rules: dict | None = None) -> None:
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
        plan["economics"] = plan_economics(plan, request, county, data, rules)
    listed = {s["id"] for s in result["sources"]}
    result["sources"] = result["sources"] + [s for s in data["sources"] if s["id"] not in listed]
    result["assumptions"] = list(dict.fromkeys(result["assumptions"] + ASSUMPTIONS))
