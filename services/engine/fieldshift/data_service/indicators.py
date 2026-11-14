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
