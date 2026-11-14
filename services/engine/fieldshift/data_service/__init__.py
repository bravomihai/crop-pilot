"""P2 owns this interface. Return crop-independent data and source metadata."""

import os
from datetime import datetime, timezone

from .climate import climate_context
from .daily import clean_daily
from .indicators import monthly_temperature_summary
from .power import fetch_power
from .soil import fetch_soil
from .terrain import fetch_slope


def build_environment(request: dict) -> dict:
    if os.getenv("ENABLE_NASA_POWER") != "true":
        raise NotImplementedError(
            "NASA data ingestion is disabled; configure and validate P2 integration"
        )
    years = int(os.getenv("HISTORY_YEARS", "20"))
    if not 1 <= years <= 45:
        raise ValueError("HISTORY_YEARS must be between 1 and 45")
    end = datetime.now(timezone.utc).year - 1
    location = request["location"]
    latitude = float(location["latitude"])
    longitude = float(location["longitude"])
    power = fetch_power(latitude, longitude, max(1981, end - years + 1), end)
    elevation = power.get("elevation_m")
    raw_daily = power.get("daily", [])
    daily, quality = clean_daily(raw_daily, latitude, elevation)
    data_gaps = list(power.get("data_gaps", []))
    sources = list(power["sources"])
    assumptions = [
        "Weather is NASA POWER daily data for the grid cell around the point, not field measurements.",
        "Reference evapotranspiration uses FAO-56 Penman-Monteith when inputs are available and Hargreaves otherwise.",
    ]
    if elevation is None:
        data_gaps.append(
            "NASA POWER returned no elevation; ET0 falls back to Hargreaves when "
            "temperature inputs are available."
        )
    hargreaves_days = quality["et0_methods"]["hargreaves"]
    if hargreaves_days:
        data_gaps.append(
            f"{hargreaves_days} days used Hargreaves ET0 because vapour pressure, "
            "wind, radiation, or elevation inputs were unavailable."
        )
    missing_core_days = sum(
        1
        for day in daily
        if any(day[key] is None for key in ("tmin", "tmax", "precip"))
    )
    if missing_core_days:
        data_gaps.append(
            f"{missing_core_days} days lack temperature or precipitation inputs "
            "in the NASA POWER record."
        )

    soil, soil_sources, soil_gaps = fetch_soil(latitude, longitude)
    sources.extend(soil_sources)
    data_gaps.extend(soil_gaps)
    static = {}
    if elevation is not None:
        static["elevation_m"] = elevation
    if soil is not None:
        static["soil"] = soil
        assumptions.append(
            "Soil is the ISRIC SoilGrids 0–30 cm modelled estimate at 250 m, not a field analysis."
        )
    slope_pct, terrain_sources, terrain_gaps = fetch_slope(latitude, longitude)
    sources.extend(terrain_sources)
    data_gaps.extend(terrain_gaps)
    if slope_pct is not None:
        static["slope_pct"] = slope_pct
    assumptions.append(
        "SRTM slope is estimated from a 3×3 elevation neighborhood around the submitted point, "
        "not across the whole field; the public OpenTopoData API receives the point coordinates."
    )

    environment = {
        "location": {"latitude": latitude, "longitude": longitude},
        "period": power["period"],
        "daily": daily,
        "monthly_climate": monthly_temperature_summary(raw_daily),
        "static": static,
        "sources": sources,
        "data_gaps": list(dict.fromkeys(data_gaps)),
        "assumptions": assumptions,
        "quality": quality,
        "retrieved_at": power.get("retrieved_at"),
    }
    climate = climate_context(daily, ["nasa-power"])
    if climate is not None:
        environment["climate_context"] = climate
    return environment
