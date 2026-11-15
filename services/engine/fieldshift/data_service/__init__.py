"""P2 owns this interface. Return crop-independent data and source metadata."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timezone

from ..geography import field_sample_points
from . import soil as soil_service
from .climate import climate_context
from .daily import clean_daily
from .indicators import monthly_temperature_summary
from .power import fetch_power
from .soil import fetch_soil
from .terrain import fetch_slope, fetch_slopes


SOIL_NUMERIC_FIELDS = (
    "clay_pct",
    "sand_pct",
    "silt_pct",
    "ph",
    "organic_carbon_pct",
)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _aggregate_soil(
    observations: list[tuple[dict | None, list[dict], list[str]]],
) -> tuple[dict | None, list[dict], list[str]]:
    available = [soil for soil, _, _ in observations if soil is not None]
    sources = []
    seen_sources = set()
    gaps = []
    for _, soil_sources, soil_gaps in observations:
        for source in soil_sources:
            if source.get("id") not in seen_sources:
                sources.append(source)
                seen_sources.add(source.get("id"))
        gaps.extend(soil_gaps)
    if not available:
        return None, sources, list(dict.fromkeys(gaps))
    if len(available) < len(observations):
        gaps.append(
            f"SoilGrids estimates were available at {len(available)} of "
            f"{len(observations)} field sample points; averages use available samples."
        )

    soil = {"depth": "0-30 cm", "source": "soilgrids"}
    for field in SOIL_NUMERIC_FIELDS:
        values = [
            row[field]
            for row in available
            if isinstance(row.get(field), (int, float))
            and not isinstance(row.get(field), bool)
        ]
        mean = _mean(values)
        if mean is not None:
            soil[field] = mean

    if all(field in soil for field in ("clay_pct", "sand_pct", "silt_pct")):
        soil["texture"] = soil_service.texture_class(
            soil["clay_pct"], soil["sand_pct"], soil["silt_pct"]
        )
        soil["awc_m3_m3"] = soil_service.available_water(
            soil["clay_pct"],
            soil["sand_pct"],
            soil.get("organic_carbon_pct"),
        )
    else:
        awc_values = [
            row["awc_m3_m3"]
            for row in available
            if isinstance(row.get("awc_m3_m3"), (int, float))
            and not isinstance(row.get("awc_m3_m3"), bool)
        ]
        mean_awc = _mean(awc_values)
        if mean_awc is not None:
            soil["awc_m3_m3"] = mean_awc
        textures = [row["texture"] for row in available if row.get("texture")]
        if textures:
            soil["texture"] = max(
                textures,
                key=lambda value: (textures.count(value), -textures.index(value)),
            )
    return soil, sources, list(dict.fromkeys(gaps))


def build_environment(request: dict) -> dict:
    if os.getenv("ENABLE_NASA_POWER") != "true":
        raise NotImplementedError(
            "NASA data ingestion is disabled; configure and validate P2 integration"
        )
    years = int(os.getenv("HISTORY_YEARS", "20"))
    # About 65 KB of daily POWER data per year: above ~30 years an entry exceeds the shared
    # (web) cache's 2 MB limit and only the local disk cache (FIELDSHIFT_CACHE_DIR) keeps it.
    if not 1 <= years <= 45:
        raise ValueError("HISTORY_YEARS must be between 1 and 45")
    end = datetime.now(timezone.utc).year - 1
    location = request["location"]
    latitude = float(location["latitude"])
    longitude = float(location["longitude"])
    field_boundary = request.get("field_boundary")
    sample_points = (
        field_sample_points(field_boundary, location)
        if field_boundary
        else [{"latitude": latitude, "longitude": longitude}]
    )
    # The three providers are independent: query them in parallel under one deadline that
    # leaves room for evaluation inside the web app's 90 s ENGINE_TIMEOUT_MS. NASA POWER is
    # required; SoilGrids and SRTM are optional and become data gaps when late.
    deadline = time.monotonic() + float(os.getenv("DATA_DEADLINE_S", "60"))
    remaining = lambda: max(0.0, deadline - time.monotonic())
    pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="p2-fetch")

    def fetch_soil_data():
        if not field_boundary:
            return fetch_soil(latitude, longitude)
        return _aggregate_soil(
            [
                soil_service.fetch_soil(point["latitude"], point["longitude"])
                for point in sample_points
            ]
        )

    def fetch_slope_data():
        if field_boundary:
            return fetch_slopes(
                [(point["latitude"], point["longitude"]) for point in sample_points]
            )
        slope, sources, gaps = fetch_slope(latitude, longitude)
        return [slope], sources, gaps

    try:
        power_job = pool.submit(fetch_power, latitude, longitude, max(1981, end - years + 1), end)
        soil_job = pool.submit(fetch_soil_data)
        slope_job = pool.submit(fetch_slope_data)
        try:
            power = power_job.result(timeout=remaining())
        except FutureTimeout as error:
            raise TimeoutError("NASA POWER did not respond within the data deadline") from error
        try:
            soil_result = soil_job.result(timeout=remaining())
        except FutureTimeout:
            soil_result = (
                None,
                [],
                ["SoilGrids did not respond in time; soil properties are unknown."],
            )
        try:
            slope_result = slope_job.result(timeout=remaining())
        except FutureTimeout:
            slope_result = (
                [None] * len(sample_points),
                [],
                [
                    "SRTM slope did not respond in time; erosion risk is not included "
                    "in the soil score."
                ],
            )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    elevation = power.get("elevation_m")
    raw_daily = power.get("daily", [])
    daily, quality = clean_daily(raw_daily, latitude, elevation)
    data_gaps = list(power.get("data_gaps", []))
    sources = list(power["sources"])
    assumptions = [
        "Weather is NASA POWER daily data for the grid cell around the point, "
        "not field measurements.",
        "Reference evapotranspiration uses FAO-56 Penman-Monteith when inputs "
        "are available and Hargreaves otherwise.",
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

    soil, soil_sources, soil_gaps = soil_result
    sources.extend(soil_sources)
    data_gaps.extend(soil_gaps)
    static = {}
    if elevation is not None:
        static["elevation_m"] = elevation
    if soil is not None:
        static["soil"] = soil
        assumptions.append(
            "Soil is the ISRIC SoilGrids 0–30 cm modelled estimate at 250 m, "
            "not a field analysis."
        )
    slope_values, terrain_sources, terrain_gaps = slope_result
    sources.extend(terrain_sources)
    data_gaps.extend(terrain_gaps)
    valid_slopes = [slope for slope in slope_values if slope is not None]
    slope_pct = _mean(valid_slopes)
    if slope_pct is not None:
        static["slope_pct"] = slope_pct
    if field_boundary:
        if len(valid_slopes) < len(sample_points):
            data_gaps.append(
                f"SRTM slope was available at {len(valid_slopes)} of "
                f"{len(sample_points)} field sample points; the mean uses available samples."
            )
        assumptions.append(
            "Sparse SoilGrids and SRTM samples are arithmetic means from up to three "
            "distributed points inside the field boundary, not full-area raster statistics."
        )
        assumptions.append(
            "NASA POWER weather remains regional grid-cell data sampled at the "
            "representative point."
        )
    else:
        assumptions.append(
            "SRTM slope is estimated from a 3×3 elevation neighborhood around the "
            "submitted point, not across the whole field; the public OpenTopoData "
            "API receives the point coordinates."
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
