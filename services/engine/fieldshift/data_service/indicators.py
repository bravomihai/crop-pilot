"""Derived daily indicators from NASA POWER meteorological observations."""

import math
from datetime import datetime


def monthly_temperature_summary(daily: list[dict]) -> list[dict]:
    """Aggregate observed daily highs/lows without filling missing values."""
    months = {}
    for entry in daily:
        month = datetime.strptime(entry["date"], "%Y-%m-%d").strftime("%Y-%m")
        bucket = months.setdefault(
            month,
            {
                "max_sum": 0.0,
                "max_count": 0,
                "max_extreme": None,
                "min_sum": 0.0,
                "min_count": 0,
                "min_extreme": None,
            },
        )
        values = entry.get("values", {})
        for key, sum_key, count_key, extreme_key, choose in (
            ("T2M_MAX", "max_sum", "max_count", "max_extreme", max),
            ("T2M_MIN", "min_sum", "min_count", "min_extreme", min),
        ):
            try:
                temperature = float(values[key])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(temperature):
                continue
            bucket[sum_key] += temperature
            bucket[count_key] += 1
            current_extreme = bucket[extreme_key]
            bucket[extreme_key] = (
                temperature
                if current_extreme is None
                else choose(current_extreme, temperature)
            )

    return [
        {
            "month": month,
            "mean_daily_max_c": round(bucket["max_sum"] / bucket["max_count"], 2)
            if bucket["max_count"]
            else None,
            "max_daily_max_c": bucket["max_extreme"],
            "mean_daily_min_c": round(bucket["min_sum"] / bucket["min_count"], 2)
            if bucket["min_count"]
            else None,
            "min_daily_min_c": bucket["min_extreme"],
            "max_temp_observations": bucket["max_count"],
            "min_temp_observations": bucket["min_count"],
        }
        for month, bucket in sorted(months.items())
    ]


def _saturation_vapor_pressure(temp_c: float) -> float:
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def _extraterrestrial_radiation(latitude: float, day_of_year: int) -> float:
    latitude_rad = math.radians(latitude)
    inverse_distance = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    sunset_angle = math.acos(
        max(
            -1.0,
            min(1.0, -math.tan(latitude_rad) * math.tan(declination)),
        )
    )
    return (
        (24 * 60 / math.pi)
        * 0.0820
        * inverse_distance
        * (
            sunset_angle * math.sin(latitude_rad) * math.sin(declination)
            + math.cos(latitude_rad)
            * math.cos(declination)
            * math.sin(sunset_angle)
        )
    )


def reference_et0_mm(
    values: dict,
    latitude: float,
    elevation_m: float | None,
    day_of_year: int,
    temp_change_c: float = 0,
) -> float | None:
    """FAO-56 daily Penman-Monteith ET0 in mm/day; None when inputs are missing."""
    required = ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN")
    if elevation_m is None or any(values.get(name) is None for name in required):
        return None

    try:
        tmean, tmin, tmax = (
            float(values[name]) + temp_change_c
            for name in ("T2M", "T2M_MIN", "T2M_MAX")
        )
        humidity = max(0.0, min(100.0, float(values["RH2M"])))
        wind = max(0.0, float(values["WS2M"]))
        solar = max(0.0, float(values["ALLSKY_SFC_SW_DWN"]))
        elevation = float(elevation_m)
    except (TypeError, ValueError):
        return None

    es = (_saturation_vapor_pressure(tmax) + _saturation_vapor_pressure(tmin)) / 2
    ea = es * humidity / 100
    delta = (
        4098
        * _saturation_vapor_pressure(tmean)
        / (tmean + 237.3) ** 2
    )
    pressure = 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    psychrometric_constant = 0.000665 * pressure

    ra = _extraterrestrial_radiation(latitude, day_of_year)
    clear_sky = (0.75 + 2e-5 * elevation) * ra
    if clear_sky <= 0:
        return None
    cloudiness = max(0.3, min(solar / clear_sky, 1.0))
    mean_kelvin_fourth = ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2
    net_longwave = (
        4.903e-9
        * mean_kelvin_fourth
        * (0.34 - 0.14 * math.sqrt(max(ea, 0)))
        * (1.35 * cloudiness - 0.35)
    )
    net_radiation = 0.77 * solar - net_longwave
    et0 = (
        0.408 * delta * net_radiation
        + psychrometric_constant
        * (900 / (tmean + 273))
        * wind
        * (es - ea)
    ) / (delta + psychrometric_constant * (1 + 0.34 * wind))
    if not math.isfinite(et0):
        return None
    return round(max(et0, 0), 4)
