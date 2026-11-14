"""Observed yearly climate at the location, for the results page (contract `climate_context`).

Computed from the same daily data the plans are evaluated on, with no scenario applied:
it describes what happened, not a hypothesis. Crop-independent; it could move to the data
service (P2) later without changing its output.
"""

from __future__ import annotations

from datetime import date, timedelta

from .weather import build_weather

HOT_DAY_C = 32.0
FROST_C = 0.0
HEAVY_RAIN_MM = 20.0
DRY_DAY_MM = 1.0
MIN_TREND_YEARS = 10

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
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    return 0.0 if var == 0 else 10 * sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var


def _year_summary(weather, start: int, end: int, year: int) -> dict:
    tmin, tmax, tmean = weather.tmin[start:end], weather.tmax[start:end], weather.tmean[start:end]
    rain, et0 = weather.precip[start:end], weather.et0[start:end]
    first = date(year, 1, 1)
    july = (date(year, 7, 1) - first).days
    april, october = (date(year, 4, 1) - first).days, (date(year, 10, 1) - first).days
    spring = [i for i in range(0, july) if tmin[i] <= FROST_C]
    autumn = [i for i in range(july, len(tmin)) if tmin[i] <= FROST_C]
    longest = run = 0
    for i in range(april, october):
        run = run + 1 if rain[i] < DRY_DAY_MM else 0
        longest = max(longest, run)
    return {
        "year": year,
        "rain_mm": round(sum(rain)),
        "et0_mm": round(sum(et0)),
        "tmean_c": round(sum(tmean) / len(tmean), 2),
        "hot_days_gt32": sum(1 for t in tmax if t > HOT_DAY_C),
        "frost_days": sum(1 for t in tmin if t <= FROST_C),
        "heavy_rain_days_gt20mm": sum(1 for r in rain if r > HEAVY_RAIN_MM),
        "dry_spell_max_days_apr_sep": longest,
        "last_spring_frost_doy": spring[-1] + 1 if spring else None,
        "first_autumn_frost_doy": autumn[0] + 1 if autumn else None,
    }


def climate_context(environment: dict, location: dict) -> dict | None:
    """Per-year observed indicators and their linear trends; None without daily data."""
    if not isinstance(environment, dict):
        return None
    elevation = None
    static = environment.get("static") if isinstance(environment.get("static"), dict) else {}
    if isinstance(static.get("elevation_m"), (int, float)):
        elevation = float(static["elevation_m"])
    weather = build_weather(environment, float(location["latitude"]), elevation or 0.0)
    if weather is None:
        return None
    years = []
    for year in range(weather.start.year, weather.end.year + 1):
        first, last = date(year, 1, 1), date(year, 12, 31)
        if first < weather.start or last > weather.end:
            continue  # only complete calendar years
        years.append(_year_summary(weather, weather.index(first), weather.index(last) + 1, year))
    if not years:
        return None
    trends = {}
    if len(years) >= MIN_TREND_YEARS:
        for key, unit in UNITS.items():
            pairs = [(y["year"], y[key]) for y in years if y[key] is not None]
            if len(pairs) >= MIN_TREND_YEARS:
                xs, ys = [p[0] for p in pairs], [float(p[1]) for p in pairs]
                trends[key] = {
                    "mean": round(sum(ys) / len(ys), 2),
                    "per_decade": round(_slope_per_decade(xs, ys), 2),
                    "unit": unit,
                }
    source_ids = [str(s["id"]) for s in environment.get("sources") or [] if isinstance(s, dict) and s.get("id")]
    note = (
        "Observed values at this point from the data the plans were evaluated on; regional "
        "(NASA POWER grid), not field measurements. Trends are simple linear fits over a short "
        "period and change noticeably with the first and last years; read them as direction, not rate."
    )
    if weather.filled_days:
        note += f" {weather.filled_days} missing daily values were filled."
    return {
        "basis": "observed",
        "period": {"start_year": years[0]["year"], "end_year": years[-1]["year"]},
        "years": years,
        "trends": trends,
        "source_ids": source_ids,
        "note": note,
    }
