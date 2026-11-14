"""Turn P2's environment into daily series the evaluator can replay.

Accepted `environment["daily"]` entries (P2 may use either naming):
  {"date": "YYYY-MM-DD", "values": {"T2M_MIN": .., "T2M_MAX": .., "T2M": .., "PRECTOTCORR": ..,
                                     "RH2M": .., "WS2M": .., "ALLSKY_SFC_SW_DWN": .., "T2MDEW": ..}}
  {"date": "YYYY-MM-DD", "tmin": .., "tmax": .., "tmean": .., "precip": .., "rh": .., "wind": ..,
   "solar": .., "dewpoint": .., "et0": ..}
Units: °C, mm/day, %, m/s at 2 m, MJ/m²/day. Missing values are None.

Reference evapotranspiration is FAO-56 Penman-Monteith when humidity, wind and radiation
are present, otherwise Hargreaves (FAO-56 eq. 52). A supplied `et0` is used only when no
scenario is requested, because the scenario changes temperature.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

ALIASES = {
    "tmin": ("tmin", "T2M_MIN"),
    "tmax": ("tmax", "T2M_MAX"),
    "tmean": ("tmean", "T2M"),
    "precip": ("precip", "precip_mm", "PRECTOTCORR"),
    "rh": ("rh", "RH2M"),
    "wind": ("wind", "WS2M"),
    "solar": ("solar", "ALLSKY_SFC_SW_DWN"),
    "dewpoint": ("dewpoint", "T2MDEW"),
    "et0": ("et0", "et0_mm"),
}


@dataclass
class Weather:
    start: date
    tmin: list[float]
    tmax: list[float]
    tmean: list[float]
    precip: list[float]
    et0: list[float]
    et0_method: str
    filled_days: int
    notes: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.tmin)

    @property
    def end(self) -> date:
        return self.start + timedelta(days=len(self) - 1)

    def index(self, day: date) -> int:
        return (day - self.start).days


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value <= -900:  # provider fill values
        return None
    return float(value)


def _pick(entry: dict, name: str) -> float | None:
    values = entry.get("values") if isinstance(entry.get("values"), dict) else {}
    for key in ALIASES[name]:
        for holder in (entry, values):
            if key in holder:
                found = _number(holder[key])
                if found is not None:
                    return found
    return None


def _svp(temp: float) -> float:
    return 0.6108 * math.exp(17.27 * temp / (temp + 237.3))


def extraterrestrial_radiation(latitude: float, day_of_year: int) -> float:
    """FAO-56 eq. 21, MJ/m²/day."""
    phi = math.radians(latitude)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )


def hargreaves(tmin: float, tmax: float, tmean: float, ra: float) -> float:
    return max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * 0.408 * ra)


def penman_monteith(tmin, tmax, tmean, ea, wind, solar, ra, elevation) -> float:
    """FAO-56 eq. 6 for a grass reference, daily step, soil heat flux 0."""
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


def build_weather(
    environment: dict, latitude: float, elevation: float, temp_change: float = 0.0, rain_change_pct: float = 0.0
) -> Weather | None:
    """Continuous daily series from the environment, with the hypothetical scenario applied.

    Temperature shifts by `temp_change`; precipitation scales by `rain_change_pct`. Actual
    vapour pressure, wind and radiation stay as observed, so warmer air is also drier air.
    Returns None when there is no usable daily data.
    """
    raw = environment.get("daily") if isinstance(environment, dict) else None
    if not isinstance(raw, list) or not raw:
        return None
    by_day: dict[date, dict] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            by_day[date.fromisoformat(str(entry.get("date")))] = entry
        except ValueError:
            continue
    if not by_day:
        return None
    start, end = min(by_day), max(by_day)
    scenario = temp_change != 0 or rain_change_pct != 0
    rain_factor = 1 + rain_change_pct / 100
    tmin_s, tmax_s, tmean_s, precip_s, et0_s = [], [], [], [], []
    filled = pm_days = hargreaves_days = supplied_days = 0
    last = {"tmin": None, "tmax": None}
    day = start
    while day <= end:
        entry = by_day.get(day, {})
        tmin, tmax = _pick(entry, "tmin"), _pick(entry, "tmax")
        if tmin is None or tmax is None:
            # Carry the last observed day forward; a gap at the very start waits for data.
            if last["tmin"] is None:
                day += timedelta(days=1)
                start = day
                continue
            tmin, tmax = last["tmin"], last["tmax"]
            filled += 1
        else:
            last["tmin"], last["tmax"] = tmin, tmax
        tmean = _pick(entry, "tmean")
        if tmean is None:
            tmean = (tmin + tmax) / 2
        precip = _pick(entry, "precip")
        if precip is None:
            precip = 0.0
            if entry:
                filled += 1
        rh, wind, solar = _pick(entry, "rh"), _pick(entry, "wind"), _pick(entry, "solar")
        dew = _pick(entry, "dewpoint")
        ea = _svp(dew) if dew is not None else (rh / 100 * (_svp(tmax) + _svp(tmin)) / 2 if rh is not None else None)
        supplied = _pick(entry, "et0")
        s_tmin, s_tmax, s_tmean = tmin + temp_change, tmax + temp_change, tmean + temp_change
        ra = extraterrestrial_radiation(latitude, day.timetuple().tm_yday)
        if supplied is not None and not scenario:
            et0 = supplied
            supplied_days += 1
        elif ea is not None and wind is not None and solar is not None:
            et0 = penman_monteith(s_tmin, s_tmax, s_tmean, ea, wind, solar, ra, elevation)
            pm_days += 1
        else:
            et0 = hargreaves(s_tmin, s_tmax, s_tmean, ra)
            hargreaves_days += 1
        tmin_s.append(s_tmin)
        tmax_s.append(s_tmax)
        tmean_s.append(s_tmean)
        precip_s.append(max(0.0, precip * rain_factor))
        et0_s.append(et0)
        day += timedelta(days=1)
    if not tmin_s:
        return None
    method = max(
        (("FAO-56 Penman-Monteith", pm_days), ("Hargreaves", hargreaves_days), ("supplied by the data service", supplied_days)),
        key=lambda item: item[1],
    )[0]
    notes = []
    if filled:
        notes.append(f"{filled} daily values were missing in the weather record and were filled (temperature carried forward, rain as 0).")
    if hargreaves_days and pm_days:
        notes.append("Reference evapotranspiration uses Hargreaves on days without humidity, wind or radiation.")
    return Weather(start, tmin_s, tmax_s, tmean_s, precip_s, et0_s, method, filled, notes)
