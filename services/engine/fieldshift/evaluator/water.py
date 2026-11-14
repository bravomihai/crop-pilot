"""Daily soil water balance, FAO-56 chapter 8 (single crop coefficient with water stress).

One profile bucket (`profile_depth_m`) carries water from one crop to the next, so a crop
that leaves the soil dry (for example sunflower) affects the crop after it. The share of
the profile a crop can use grows with its roots; depletion is assumed uniform with depth.

Simplifications (reported as assumptions): no runoff, no capillary rise, bare-soil
evaporation with a constant coefficient that falls as the profile dries.
"""

from __future__ import annotations

from dataclasses import dataclass

from .weather import Weather

INITIAL_ROOT_DEPTH_M = 0.3
STAGES = ("ini", "dev", "mid", "late")


@dataclass(frozen=True)
class Season:
    """Result of one crop season in one replayed year."""

    etc_mm: float  # crop water demand, no stress
    eta_mm: float  # water actually used
    rain_mm: float
    irrigation_mm: float
    bounds: tuple[int, int, int, int, int]  # sowing, end of ini, dev, mid, harvest (day indices)

    @property
    def wrsi(self) -> float:
        """Water Requirement Satisfaction Index, percent."""
        return 100.0 if self.etc_mm <= 0 else 100.0 * self.eta_mm / self.etc_mm


def stage_bounds(sow: int, harvest: int, fractions) -> tuple[int, int, int, int, int]:
    length = max(harvest - sow, 4)
    total = sum(fractions)
    b1 = sow + round(length * fractions[0] / total)
    b2 = b1 + round(length * fractions[1] / total)
    b3 = b2 + round(length * fractions[2] / total)
    return sow, b1, max(b2, b1 + 1), max(b3, b2 + 2), sow + length


def run_fallow(weather: Weather, start: int, end: int, depletion: float, taw_profile: float, settings: dict) -> float:
    kc, min_fraction = settings["kc_bare_soil"], settings["min_effective_rain_et0_fraction"]
    et0, precip = weather.et0, weather.precip
    for i in range(start, end):
        rain = precip[i]
        if rain < min_fraction * et0[i]:
            rain = 0.0
        depletion += kc * et0[i] * max(0.0, 1.0 - depletion / taw_profile) - rain
        if depletion < 0.0:
            depletion = 0.0  # surplus drains below the profile
        elif depletion > taw_profile:
            depletion = taw_profile
    return depletion


def run_crop(
    weather: Weather,
    sow: int,
    harvest: int,
    depletion: float,
    crop: dict,
    awc: float,
    settings: dict,
    irrigated: bool = False,
    irrigation_budget: float | None = None,
) -> tuple[float, Season]:
    profile_depth = settings["profile_depth_m"]
    taw_profile = awc * 1000 * profile_depth
    min_fraction = settings["min_effective_rain_et0_fraction"]
    kc_ini, kc_end = crop["kc"]["ini"], crop["kc"]["end"]
    kc_mid = crop["kc"]["mid_irrigated"] if irrigated else crop["kc"]["mid"]
    root_max = min(sum(crop["root_depth_m"]) / 2, profile_depth)
    p_table = crop["depletion_fraction"]
    bounds = stage_bounds(sow, harvest, crop["stage_fractions"])
    _, b1, b2, b3, end = bounds
    budget = float("inf") if irrigation_budget is None else irrigation_budget
    et0, precip = weather.et0, weather.precip
    etc_sum = eta_sum = rain_sum = irrigation_sum = 0.0
    for i in range(sow, end):
        if i < b1:
            kc = kc_ini
        elif i < b2:
            kc = kc_ini + (kc_mid - kc_ini) * (i - b1) / (b2 - b1)
        elif i < b3:
            kc = kc_mid
        else:
            kc = kc_mid + (kc_end - kc_mid) * (i - b3) / max(end - b3, 1)
        root = INITIAL_ROOT_DEPTH_M + (root_max - INITIAL_ROOT_DEPTH_M) * min(1.0, (i - sow) / max(b2 - sow, 1))
        share = root / profile_depth
        taw_root = taw_profile * share
        etc = kc * et0[i]
        p = min(0.8, max(0.1, p_table + 0.04 * (5.0 - etc)))  # FAO-56 Table 22, footnote 2
        raw = p * taw_root
        root_depletion = depletion * share
        if irrigated and root_depletion > raw and budget > 0 and i < b3:
            amount = min(root_depletion, budget)
            depletion -= amount
            budget -= amount
            irrigation_sum += amount
            root_depletion = depletion * share
        if root_depletion <= raw:
            ks = 1.0
        else:
            ks = max(0.0, (taw_root - root_depletion) / ((1.0 - p) * taw_root))
        eta = ks * etc
        rain = precip[i]
        rain_sum += rain
        if rain < min_fraction * et0[i]:
            rain = 0.0
        depletion += eta - rain
        if depletion < 0.0:
            depletion = 0.0
        elif depletion > taw_profile:
            depletion = taw_profile
        etc_sum += etc
        eta_sum += eta
    return depletion, Season(etc_sum, eta_sum, rain_sum, irrigation_sum, bounds)
