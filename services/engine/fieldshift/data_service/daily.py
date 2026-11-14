"""Clean NASA POWER daily records and calculate reference evapotranspiration."""

from __future__ import annotations

import math
from datetime import date

NAMES = {
    "tmin": "T2M_MIN",
    "tmax": "T2M_MAX",
    "tmean": "T2M",
    "precip": "PRECTOTCORR",
    "rh": "RH2M",
    "wind": "WS2M",
    "solar": "ALLSKY_SFC_SW_DWN",
    "dewpoint": "T2MDEW",
}


def _svp(temp: float) -> float:
    return 0.6108 * math.exp(17.27 * temp / (temp + 237.3))


def extraterrestrial_radiation(latitude: float, day_of_year: int) -> float:
    """FAO-56 equation 21, MJ/m²/day."""
    phi = math.radians(latitude)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )


def _penman_monteith(
    tmin: float,
    tmax: float,
    tmean: float,
    ea: float,
    wind: float,
    solar: float,
    ra: float,
    elevation: float,
) -> float:
    """FAO-56 equation 6 for the grass reference, daily step, mm/day."""
    es = (_svp(tmax) + _svp(tmin)) / 2
    slope = 4098 * _svp(tmean) / (tmean + 237.3) ** 2
    pressure = 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    gamma = 0.000665 * pressure
    rso = (0.75 + 2e-5 * elevation) * ra
    cloud = max(0.3, min(solar / rso, 1.0)) if rso > 0 else 0.3
    rnl = (
        4.903e-9
        * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4)
        / 2
        * (0.34 - 0.14 * math.sqrt(max(ea, 0.0)))
        * (1.35 * cloud - 0.35)
    )
    rn = 0.77 * solar - rnl
    wind = max(wind, 0.0)
    value = (0.408 * slope * rn + gamma * 900 / (tmean + 273) * wind * max(es - ea, 0.0)) / (
        slope + gamma * (1 + 0.34 * wind)
    )
    return max(value, 0.0)


def _hargreaves(tmin: float, tmax: float, tmean: float, ra: float) -> float:
    """FAO-56 equation 52, mm/day."""
    return max(
        0.0,
        0.0023
        * (tmean + 17.8)
        * math.sqrt(max(tmax - tmin, 0.0))
        * 0.408
        * ra,
    )


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value <= -900:
        return None
    return float(value)


def clean_daily(
    raw_daily: list[dict], latitude: float, elevation: float | None
) -> tuple[list[dict], dict]:
    """Return named daily values, ET0, and counts of missing provider values."""
    cleaned = []
    missing = {key: 0 for key in NAMES}
    methods = {"penman_monteith": 0, "hargreaves": 0, "none": 0}
    for entry in raw_daily:
        values = entry.get("values") or {}
        day = {key: _number(values.get(name)) for key, name in NAMES.items()}
        for key, value in day.items():
            if value is None:
                missing[key] += 1
        if day["tmean"] is None and day["tmin"] is not None and day["tmax"] is not None:
            day["tmean"] = (day["tmin"] + day["tmax"]) / 2

        et0, method = None, "none"
        if day["tmin"] is not None and day["tmax"] is not None and day["tmean"] is not None:
            doy = date.fromisoformat(entry["date"]).timetuple().tm_yday
            ra = extraterrestrial_radiation(latitude, doy)
            if day["dewpoint"] is not None:
                ea = _svp(day["dewpoint"])
            elif day["rh"] is not None:
                humidity = max(0.0, min(100.0, day["rh"]))
                ea = humidity / 100 * (_svp(day["tmax"]) + _svp(day["tmin"])) / 2
            else:
                ea = None
            if (
                ea is not None
                and day["wind"] is not None
                and day["solar"] is not None
                and elevation is not None
            ):
                et0 = _penman_monteith(
                    day["tmin"],
                    day["tmax"],
                    day["tmean"],
                    ea,
                    day["wind"],
                    day["solar"],
                    ra,
                    elevation,
                )
                method = "penman_monteith"
            else:
                et0 = _hargreaves(day["tmin"], day["tmax"], day["tmean"], ra)
                method = "hargreaves"
        methods[method] += 1
        cleaned.append(
            {
                "date": entry["date"],
                **{
                    key: None if value is None else round(value, 3)
                    for key, value in day.items()
                },
                "et0": None if et0 is None else round(et0, 3),
                "et0_method": method,
            }
        )
    return cleaned, {
        "days": len(cleaned),
        "missing": missing,
        "et0_methods": methods,
    }
