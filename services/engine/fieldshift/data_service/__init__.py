"""P2 owns this interface. Return crop-independent data and source metadata."""

import os
from datetime import datetime, timezone

import httpx

from .power import fetch_power
from .soilgrids import fetch_soilgrids
from .indicators import monthly_temperature_summary, reference_et0_mm


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
    latitude = location["latitude"]
    longitude = location["longitude"]
    power = fetch_power(
        latitude, longitude, max(1981, end - years + 1), end
    )
    data_gaps = list(power.get("data_gaps", []))
    daily = []
    for entry in power["daily"]:
        values = entry["values"]
        day = datetime.strptime(entry["date"], "%Y-%m-%d").date()
        daily.append(
            {
                **entry,
                "et0_mm": reference_et0_mm(
                    values,
                    latitude,
                    power["elevation_m"],
                    day.timetuple().tm_yday,
                ),
            }
        )
    if power["elevation_m"] is None:
        data_gaps.append("NASA POWER site elevation is missing; ET0 is unavailable.")

    try:
        soil = fetch_soilgrids(latitude, longitude)
    except httpx.HTTPError as error:
        soil = {
            "status": "unavailable",
            "depth_cm": "0-5",
            "properties": {},
            "data_gaps": [f"SoilGrids request failed: {error}"],
        }
    data_gaps.extend(soil["data_gaps"])
    sources = list(power["sources"])
    if soil.get("source"):
        sources.append(soil["source"])

    user_soil = request.get("soil", {})
    measured_soil = {
        key: user_soil[key]
        for key in ("texture", "ph", "organic_carbon_pct")
        if key in user_soil
    }
    return {
        **power,
        "daily": daily,
        "monthly_climate": monthly_temperature_summary(daily),
        "soil": {
            "status": "user_supplied"
            if measured_soil
            else soil["status"],
            "properties": {**soil["properties"], **measured_soil},
            "user_source": user_soil.get("source", "unknown"),
            "provider_depth_cm": soil["depth_cm"],
        },
        "sources": sources,
        "data_gaps": data_gaps,
    }
