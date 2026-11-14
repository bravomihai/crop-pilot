"""Daily soil water balance, FAO-56 chapter 8 (single crop coefficient with water stress).

The soil profile (`profile_depth_m`) holds two layers with a moving boundary:

- the upper layer: the crop's root zone (depth Zr) during a season, the 0.3 m surface
  layer during fallow. Crops take water only from here, and water stress (Ks) is computed
  from this layer alone, with TAW = AWC × Zr as in FAO-56;
- the lower layer: the rest of the profile. It stores water and is recharged by rain that
  drains through the upper layer.

Roots grow from 0.3 m at sowing to the crop's maximum depth (FAO-56 Table 22) at the start
of mid-season. Each day the root zone takes over a slice of the lower layer together with
that slice's water. A seedling therefore depends on the topsoil, a mature crop can use
water stored deeper (for example from winter rain), and a crop that dries the deep soil
leaves less for the next one.

Within each layer depletion is uniform. Simplifications (reported as assumptions): no
runoff, no capillary rise, bare-soil evaporation from the surface layer with a constant
coefficient that falls as that layer dries.
"""

from __future__ import annotations

from dataclasses import dataclass

from .weather import Weather

INITIAL_ROOT_DEPTH_M = 0.3
SURFACE_DEPTH_M = INITIAL_ROOT_DEPTH_M
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


@dataclass(frozen=True)
class SoilState:
    """Water state of the profile: upper layer depth (m) and depletion (mm) of both layers."""

    upper_depth_m: float
    upper_depletion_mm: float
    lower_depletion_mm: float


def initial_state(awc: float, settings: dict) -> SoilState:
    """Both layers at the same starting depletion fraction."""
    per_m = awc * 1000
    fraction = settings["initial_depletion_fraction"]
    profile = settings["profile_depth_m"]
    return SoilState(SURFACE_DEPTH_M, fraction * per_m * SURFACE_DEPTH_M, fraction * per_m * (profile - SURFACE_DEPTH_M))


def move_boundary(upper_depth: float, d_upper: float, d_lower: float, new_depth: float, profile: float) -> tuple[float, float]:
    """Move the layer boundary to `new_depth`, carrying the moved slice's depletion with it."""
    if new_depth > upper_depth:
        lower_depth = profile - upper_depth
        moved = d_lower * (new_depth - upper_depth) / lower_depth if lower_depth > 1e-9 else 0.0
        return d_upper + moved, d_lower - moved
    if new_depth < upper_depth:
        moved = d_upper * (upper_depth - new_depth) / upper_depth
        return d_upper - moved, d_lower + moved
    return d_upper, d_lower


def stage_bounds(sow: int, harvest: int, fractions) -> tuple[int, int, int, int, int]:
    length = max(harvest - sow, 4)
    total = sum(fractions)
    b1 = sow + round(length * fractions[0] / total)
    b2 = b1 + round(length * fractions[1] / total)
    b3 = b2 + round(length * fractions[2] / total)
    return sow, b1, max(b2, b1 + 1), max(b3, b2 + 2), sow + length


def run_fallow(weather: Weather, start: int, end: int, state: SoilState, awc: float, settings: dict) -> SoilState:
    """Bare soil: evaporation from the surface layer; rain refills it, then the layer below."""
    kc, min_fraction = settings["kc_bare_soil"], settings["min_effective_rain_et0_fraction"]
    profile = settings["profile_depth_m"]
    per_m = awc * 1000
    d_upper, d_lower = move_boundary(state.upper_depth_m, state.upper_depletion_mm, state.lower_depletion_mm, SURFACE_DEPTH_M, profile)
    taw_upper = per_m * SURFACE_DEPTH_M
    taw_lower = per_m * (profile - SURFACE_DEPTH_M)
    inverse_taw = 1.0 / taw_upper
    et0, precip = weather.et0, weather.precip
    for i in range(start, end):
        rain = precip[i]
        day_et0 = et0[i]
        if rain < min_fraction * day_et0:
            rain = 0.0
        dryness = 1.0 - d_upper * inverse_taw
        d_upper += (kc * day_et0 * dryness if dryness > 0.0 else 0.0) - rain
        if d_upper < 0.0:
            d_lower += d_upper  # surplus percolates to the lower layer
            d_upper = 0.0
            if d_lower < 0.0:
                d_lower = 0.0  # and beyond the profile
        elif d_upper > taw_upper:
            d_upper = taw_upper
    if d_lower > taw_lower:
        d_lower = taw_lower
    return SoilState(SURFACE_DEPTH_M, d_upper, d_lower)


def run_crop(
    weather: Weather,
    sow: int,
    harvest: int,
    state: SoilState,
    crop: dict,
    awc: float,
    settings: dict,
    irrigated: bool = False,
    irrigation_budget: float | None = None,
) -> tuple[SoilState, Season]:
    profile = settings["profile_depth_m"]
    per_m = awc * 1000
    min_fraction = settings["min_effective_rain_et0_fraction"]
    kc_ini, kc_end = crop["kc"]["ini"], crop["kc"]["end"]
    kc_mid = crop["kc"]["mid_irrigated"] if irrigated else crop["kc"]["mid"]
    root_start = INITIAL_ROOT_DEPTH_M
    root_max = max(root_start, min(sum(crop["root_depth_m"]) / 2, profile))
    p_table = crop["depletion_fraction"]
    bounds = stage_bounds(sow, harvest, crop["stage_fractions"])
    _, b1, b2, b3, end = bounds
    budget = float("inf") if irrigation_budget is None else irrigation_budget
    et0, precip = weather.et0, weather.precip
    etc_sum = eta_sum = rain_sum = irrigation_sum = 0.0

    zr = state.upper_depth_m
    d_root, d_lower = state.upper_depletion_mm, state.lower_depletion_mm
    if zr != root_start:
        d_root, d_lower = move_boundary(zr, d_root, d_lower, root_start, profile)
        zr = root_start
    dev_slope = (kc_mid - kc_ini) / (b2 - b1)
    late_slope = (kc_end - kc_mid) / max(end - b3, 1)
    root_step = (root_max - root_start) / max(b2 - sow, 1)

    for i in range(sow, end):
        # Root growth: take over a slice of the lower layer with its water.
        if zr < root_max:
            new_zr = zr + root_step
            if new_zr > root_max:
                new_zr = root_max
            lower_depth = profile - zr
            if lower_depth > 1e-9:
                moved = d_lower * (new_zr - zr) / lower_depth
                d_root += moved
                d_lower -= moved
            zr = new_zr
        if i < b1:
            kc = kc_ini
        elif i < b2:
            kc = kc_ini + dev_slope * (i - b1)
        elif i < b3:
            kc = kc_mid
        else:
            kc = kc_mid + late_slope * (i - b3)
        day_et0 = et0[i]
        etc = kc * day_et0
        taw_root = per_m * zr
        p = p_table + 0.04 * (5.0 - etc)  # FAO-56 Table 22, footnote 2
        if p < 0.1:
            p = 0.1
        elif p > 0.8:
            p = 0.8
        raw = p * taw_root
        if irrigated and d_root > raw and budget > 0 and i < b3:
            amount = d_root if d_root < budget else budget  # refill the root zone (FAO-56 ch. 8)
            d_root -= amount
            budget -= amount
            irrigation_sum += amount
        if d_root <= raw:
            eta = etc
        else:
            ks = (taw_root - d_root) / ((1.0 - p) * taw_root)
            eta = ks * etc if ks > 0.0 else 0.0
        rain = precip[i]
        rain_sum += rain
        if rain < min_fraction * day_et0:
            rain = 0.0
        d_root += eta - rain
        if d_root < 0.0:
            d_lower += d_root  # drainage below the roots recharges the lower layer
            d_root = 0.0
            if d_lower < 0.0:
                d_lower = 0.0
        elif d_root > taw_root:
            d_root = taw_root
        etc_sum += etc
        eta_sum += eta
    taw_lower = per_m * (profile - zr)
    if d_lower > taw_lower:
        d_lower = taw_lower
    return SoilState(zr, d_root, d_lower), Season(etc_sum, eta_sum, rain_sum, irrigation_sum, bounds)
