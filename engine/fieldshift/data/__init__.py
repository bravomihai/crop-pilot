"""Fetch and normalize environmental observations for a field."""

import math
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
POWER_PARAMETERS = (
    "PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,T2MDEW,WS2M,ALLSKY_SFC_SW_DWN"
)
CACHE_TTL_SECONDS = 6 * 60 * 60
CACHE_MAX_ENTRIES = 256
_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any], str]] = {}
_cache_lock = threading.Lock()


def _request_json(
    cache_key: tuple[Any, ...], url: str, params: dict[str, Any]
) -> tuple[dict[str, Any], str, bool]:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1], cached[2], True

    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    retrieved_at = datetime.now(timezone.utc).isoformat()

    with _cache_lock:
        _cache[cache_key] = (now, payload, retrieved_at)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.pop(next(iter(_cache)))
    return payload, retrieved_at, False


def _number(value: Any, fill_value: float) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result == fill_value:
        return None
    return result


def _extraterrestrial_radiation(latitude: float, day_of_year: int) -> float:
    """Daily FAO-56 extraterrestrial radiation in MJ/m²."""
    phi = math.radians(latitude)
    inverse_distance = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    sunset_angle = math.acos(
        max(-1.0, min(1.0, -math.tan(phi) * math.tan(declination)))
    )
    return (
        (24 * 60 / math.pi)
        * 0.0820
        * inverse_distance
        * (
            sunset_angle * math.sin(phi) * math.sin(declination)
            + math.cos(phi) * math.cos(declination) * math.sin(sunset_angle)
        )
    )


def _et0(
    tmean: float | None,
    tmin: float | None,
    tmax: float | None,
    dewpoint: float | None,
    wind: float | None,
    solar_radiation: float | None,
    elevation: float | None,
    latitude: float,
    day_of_year: int,
) -> float | None:
    """Calculate daily reference ET with the FAO-56 Penman-Monteith equation."""
    inputs = (tmean, tmin, tmax, dewpoint, wind, solar_radiation, elevation)
    if any(value is None for value in inputs):
        return None
    assert tmean is not None
    assert tmin is not None
    assert tmax is not None
    assert dewpoint is not None
    assert wind is not None
    assert solar_radiation is not None
    assert elevation is not None

    saturation_vapor_pressure = 0.6108 * math.exp(
        17.27 * tmean / (tmean + 237.3)
    )
    actual_vapor_pressure = 0.6108 * math.exp(
        17.27 * dewpoint / (dewpoint + 237.3)
    )
    slope = (
        4098
        * saturation_vapor_pressure
        / (tmean + 237.3) ** 2
    )
    pressure = 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    psychrometric_constant = 0.000665 * pressure

    ra = _extraterrestrial_radiation(latitude, day_of_year)
    clear_sky_radiation = (0.75 + 2e-5 * elevation) * ra
    if clear_sky_radiation <= 0:
        return None
    cloudiness = max(0.3, min(solar_radiation / clear_sky_radiation, 1.0))
    mean_kelvin_fourth = (
        (tmax + 273.16) ** 4 + (tmin + 273.16) ** 4
    ) / 2
    net_longwave = (
        4.903e-9
        * mean_kelvin_fourth
        * (0.34 - 0.14 * math.sqrt(max(actual_vapor_pressure, 0)))
        * (1.35 * cloudiness - 0.35)
    )
    net_radiation = 0.77 * solar_radiation - net_longwave
    value = (
        0.408 * slope * net_radiation
        + psychrometric_constant
        * (900 / (tmean + 273))
        * max(wind, 0)
        * (saturation_vapor_pressure - actual_vapor_pressure)
    ) / (
        slope + psychrometric_constant * (1 + 0.34 * max(wind, 0))
    )
    return max(value, 0.0)


def _soil_value(payload: dict[str, Any], name: str) -> float | None:
    for layer in payload["properties"]["layers"]:
        if layer["name"] == name:
            depth = next(
                (item for item in layer["depths"] if item["label"] == "0-5cm"),
                None,
            )
            if depth is None:
                return None
            raw = _number(depth["values"]["mean"], -999)
            if raw is None:
                return None
            factor = layer["unit_measure"]["d_factor"]
            return raw / factor
    return None


def _fetch_soil(
    lat: float, lon: float
) -> tuple[dict[str, float] | None, dict[str, Any] | None, str | None]:
    params = {
        "lon": lon,
        "lat": lat,
        "property": ["phh2o", "soc"],
        "depth": "0-5cm",
        "value": "mean",
    }
    try:
        payload, retrieved_at, from_cache = _request_json(
            ("soilgrids", round(lat, 3), round(lon, 3)),
            SOILGRIDS_URL,
            params,
        )
    except httpx.HTTPError as error:
        return None, None, str(error)

    ph = _soil_value(payload, "phh2o")
    organic_carbon = _soil_value(payload, "soc")
    values = {}
    if ph is not None:
        values["ph"] = ph
    if organic_carbon is not None:
        values["organic_carbon_pct"] = organic_carbon / 10
    source = {
        "id": "soilgrids",
        "dataset": "ISRIC SoilGrids 2.0, 0-5 cm",
        "resolution": "250 m",
        "url": SOILGRIDS_URL,
        "retrieved_at": retrieved_at,
        "from_cache": from_cache,
    }
    return (values or None), source, None


def _aggregate_year(
    year: int,
    daily: dict[str, dict[str, Any]],
    fill_value: float,
    elevation: float | None,
    latitude: float,
) -> dict[str, Any]:
    monthly_precip: list[list[float]] = [[] for _ in range(12)]
    monthly_et0: list[list[float]] = [[] for _ in range(12)]
    monthly_tmean: list[list[float]] = [[] for _ in range(12)]
    frost_doys: list[int] = []
    daily_values: list[dict[str, float | int | None]] = []

    for date in sorted(daily):
        doy = datetime.strptime(date, "%Y%m%d").timetuple().tm_yday
        month = int(date[4:6]) - 1
        values = {
            key: _number(daily[date].get(parameter), fill_value)
            for key, parameter in (
                ("precip", "PRECTOTCORR"),
                ("tmean", "T2M"),
                ("tmin", "T2M_MIN"),
                ("tmax", "T2M_MAX"),
                ("dewpoint", "T2MDEW"),
                ("wind", "WS2M"),
                ("solar", "ALLSKY_SFC_SW_DWN"),
            )
        }
        et0 = _et0(
            values["tmean"],
            values["tmin"],
            values["tmax"],
            values["dewpoint"],
            values["wind"],
            values["solar"],
            elevation,
            latitude,
            doy,
        )
        if values["precip"] is not None:
            monthly_precip[month].append(values["precip"])
        if et0 is not None:
            monthly_et0[month].append(et0)
        if values["tmean"] is not None:
            monthly_tmean[month].append(values["tmean"])
        if values["tmin"] is not None and values["tmin"] < 0:
            frost_doys.append(doy)
        daily_values.append({**values, "et0": et0, "doy": doy})

    def monthly_sum(values: list[list[float]]) -> list[float | None]:
        return [round(sum(month), 2) if month else None for month in values]

    def monthly_mean(values: list[list[float]]) -> list[float | None]:
        return (
            [round(sum(month) / len(month), 2) if month else None for month in values]
        )

    year_result: dict[str, Any] = {
        "year": year,
        "monthly": {
            "precip_mm": monthly_sum(monthly_precip),
            "et0_mm": monthly_sum(monthly_et0),
            "tmean_c": monthly_mean(monthly_tmean),
        },
    }
    precip = [value for month in monthly_precip for value in month]
    et0_values = [value for month in monthly_et0 for value in month]
    temperatures = [item["tmean"] for item in daily_values if item["tmean"] is not None]
    minimums = [item["tmin"] for item in daily_values if item["tmin"] is not None]
    maximums = [item["tmax"] for item in daily_values if item["tmax"] is not None]

    if precip:
        year_result["precip_mm"] = round(sum(precip), 2)
        year_result["heavy_rain_days_gt20mm"] = sum(
            value is not None and value > 20
            for value in (item["precip"] for item in daily_values)
        )
    if et0_values:
        year_result["et0_mm"] = round(sum(et0_values), 2)
    if temperatures:
        year_result["gdd_base10"] = round(
            sum(max(value - 10, 0) for value in temperatures), 2
        )
    if minimums:
        year_result["frost_days"] = len(frost_doys)
        spring_frosts = [doy for doy in frost_doys if doy <= 183]
        autumn_frosts = [doy for doy in frost_doys if doy > 183]
        year_result["last_spring_frost_doy"] = (
            max(spring_frosts) if spring_frosts else None
        )
        year_result["first_autumn_frost_doy"] = (
            min(autumn_frosts) if autumn_frosts else None
        )
    if maximums:
        year_result["heat_days_gt32"] = sum(
            value > 32
            for value in (item["tmax"] for item in daily_values)
            if value is not None
        )
    return year_result


def fetch_field_data(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    """Fetch NASA POWER weather and SoilGrids soil properties for a location."""
    if not -90 <= lat <= 90:
        raise ValueError("lat must be between -90 and 90")
    if not -180 <= lon <= 180:
        raise ValueError("lon must be between -180 and 180")
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")

    lat, lon = round(lat, 3), round(lon, 3)
    power_params = {
        "parameters": POWER_PARAMETERS,
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": f"{start_year}0101",
        "end": f"{end_year}1231",
        "format": "JSON",
    }
    power, retrieved_at, power_from_cache = _request_json(
        ("nasa_power", lat, lon, start_year, end_year),
        POWER_URL,
        power_params,
    )
    properties = power["properties"]
    parameter_data = properties["parameter"]
    fill_value = float(power["header"].get("fill_value", -999))
    coordinates = power["geometry"]["coordinates"]
    elevation = _number(coordinates[2], fill_value) if len(coordinates) > 2 else None

    missing: list[str] = []
    notes: list[str] = []
    static: dict[str, Any] = {}
    if elevation is not None:
        static["elevation_m"] = elevation
    else:
        missing.append("static.elevation_m")

    soil, soil_source, soil_error = _fetch_soil(lat, lon)
    sources = [
        {
            "id": "nasa_power",
            "dataset": "NASA POWER daily AG meteorology",
            "resolution": "0.5° x 0.625°",
            "url": "https://power.larc.nasa.gov/",
            "retrieved_at": retrieved_at,
            "from_cache": power_from_cache,
        }
    ]
    if soil:
        static["soil"] = {**soil, "source": "soilgrids"}
        assert soil_source is not None
        sources.append(soil_source)
    else:
        missing.append("static.soil")
        if soil_error:
            notes.append(f"SoilGrids unavailable: {soil_error}")
        else:
            notes.append("SoilGrids returned no values for this location.")

    grouped: dict[int, dict[str, dict[str, Any]]] = {
        year: {} for year in range(start_year, end_year + 1)
    }
    for parameter, observations in parameter_data.items():
        for date, value in observations.items():
            year = int(date[:4])
            if year in grouped:
                grouped[year].setdefault(date, {})[parameter] = value
    years = [
        _aggregate_year(year, grouped[year], fill_value, elevation, lat)
        for year in range(start_year, end_year + 1)
    ]

    missing.extend(
        [
            "static.slope_pct (SRTM not integrated)",
            "years[].soil_moisture_rootzone (SMAP not integrated)",
            "scenario_deltas (NEX-GDDP-CMIP6 not integrated)",
        ]
    )
    notes.append(
        "ET0 is calculated with FAO-56 Penman-Monteith from NASA POWER daily weather."
    )

    return {
        "location": {"lat": lat, "lon": lon},
        "period": {"start_year": start_year, "end_year": end_year},
        "sources": sources,
        "static": static,
        "years": years,
        "quality": {"missing": missing, "notes": notes},
    }
