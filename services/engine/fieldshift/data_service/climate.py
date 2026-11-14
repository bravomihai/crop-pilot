"""Observed yearly climate summaries computed from cleaned NASA POWER records."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

HOT_DAY_C = 32.0
FROST_C = 0.0
HEAVY_RAIN_MM = 20.0
DRY_DAY_MM = 1.0
MIN_TREND_YEARS = 10
MAX_MISSING_DAYS = 10

UNITS = {
    "rain_mm": "mm per year",
    "et0_mm": "mm per year",
    "tmean_c": "°C",
    "hot_days_gt32": "days per year",
    "frost_days": "days per year",
    "heavy_rain_days_gt20mm": "days per year",
    "dry_spell_max_days_apr_sep": "days",
    "last_spring_frost_doy": "day of year",
    "first_autumn_frost_doy": "day of year",
}


def _slope_per_decade(xs: list[int], ys: list[float]) -> float:
    count = len(xs)
    mean_x, mean_y = sum(xs) / count, sum(ys) / count
    variance = sum((x - mean_x) ** 2 for x in xs)
    if variance == 0:
        return 0.0
    return 10 * sum(
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)
    ) / variance


def _summary(year: int, days: list[dict]) -> dict | None:
    start = date(year, 1, 1)
    length = (date(year + 1, 1, 1) - start).days
    expected = {start + timedelta(days=offset) for offset in range(length)}
    dates = {date.fromisoformat(day["date"]) for day in days}
    if len(days) != length or dates != expected:
        return None

    missing_core = sum(
        1
        for day in days
        if day["tmin"] is None or day["tmax"] is None or day["precip"] is None
    )
    if missing_core > MAX_MISSING_DAYS:
        return None

    tmin = [day["tmin"] for day in days]
    tmax = [day["tmax"] for day in days]
    tmean = [day["tmean"] for day in days]
    rain = [day["precip"] for day in days]
    et0 = [day["et0"] for day in days]
    july = (date(year, 7, 1) - start).days
    april = (date(year, 4, 1) - start).days
    october = (date(year, 10, 1) - start).days

    frost_days = [i for i, temp in enumerate(tmin) if temp is not None and temp <= FROST_C]
    spring_frost = [i for i in frost_days if i < july]
    autumn_frost = [i for i in frost_days if i >= july]
    longest_dry_spell = None
    if all(value is not None for value in rain):
        longest = run = 0
        for amount in rain[april:october]:
            run = run + 1 if amount < DRY_DAY_MM else 0
            longest = max(longest, run)
        longest_dry_spell = longest

    complete_rain = all(value is not None for value in rain)
    complete_tmin = all(value is not None for value in tmin)
    complete_tmax = all(value is not None for value in tmax)
    complete_tmean = all(value is not None for value in tmean)
    complete_et0 = all(value is not None for value in et0)

    return {
        "year": year,
        "rain_mm": round(sum(rain)) if complete_rain else None,
        "et0_mm": round(sum(et0)) if complete_et0 else None,
        "tmean_c": round(sum(tmean) / length, 2) if complete_tmean else None,
        "hot_days_gt32": (
            sum(1 for temp in tmax if temp > HOT_DAY_C) if complete_tmax else None
        ),
        "frost_days": len(frost_days) if complete_tmin else None,
        "heavy_rain_days_gt20mm": (
            sum(1 for amount in rain if amount > HEAVY_RAIN_MM)
            if complete_rain
            else None
        ),
        "dry_spell_max_days_apr_sep": longest_dry_spell,
        "last_spring_frost_doy": (
            spring_frost[-1] + 1 if complete_tmin and spring_frost else None
        ),
        "first_autumn_frost_doy": (
            autumn_frost[0] + 1 if complete_tmin and autumn_frost else None
        ),
    }


def climate_context(daily: list[dict], source_ids: list[str]) -> dict | None:
    """Return observed yearly indicators; omit incomplete years and avoid filling gaps."""
    by_year: dict[int, list[dict]] = defaultdict(list)
    for day in daily:
        by_year[int(day["date"][:4])].append(day)
    years = [
        summary
        for year in sorted(by_year)
        if (summary := _summary(year, by_year[year])) is not None
    ]
    if not years:
        return None

    trends = {}
    if len(years) >= MIN_TREND_YEARS:
        for key, unit in UNITS.items():
            pairs = [(row["year"], row[key]) for row in years if row[key] is not None]
            if len(pairs) >= MIN_TREND_YEARS:
                xs = [pair[0] for pair in pairs]
                ys = [float(pair[1]) for pair in pairs]
                trends[key] = {
                    "mean": round(sum(ys) / len(ys), 2),
                    "per_decade": round(_slope_per_decade(xs, ys), 2),
                    "unit": unit,
                }

    return {
        "basis": "observed",
        "period": {
            "start_year": years[0]["year"],
            "end_year": years[-1]["year"],
        },
        "years": years,
        "trends": trends,
        "source_ids": list(source_ids),
        "note": (
            "Observed values at this point on the regional NASA POWER grid, not field "
            "measurements. Annual indicators are left null when their input series has "
            "missing days. Trends are simple linear fits; read them as direction, not rate."
        ),
    }
