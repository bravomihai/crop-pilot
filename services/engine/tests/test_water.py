"""Two-layer FAO-56 water balance: the root zone deepens and only it supplies the crop."""

from datetime import date

import pytest

from fieldshift.evaluator import load_rules
from fieldshift.evaluator.water import SoilState, initial_state, run_crop, run_fallow
from fieldshift.evaluator.weather import Weather

AWC = 0.15


@pytest.fixture(scope="module")
def setup():
    rules = load_rules({"latitude": 44.5, "longitude": 27.0})
    return rules["settings"], {c["id"]: c for c in rules["crops"]}


def dry_weather(days=200, et0=5.0, rain=0.0):
    return Weather(date(2020, 4, 1), [12.0] * days, [28.0] * days, [20.0] * days, [rain] * days, [et0] * days, "test", 0)


def test_water_balance_closes(setup):
    settings, crops = setup
    weather = dry_weather(rain=1.5)
    start = initial_state(AWC, settings)
    total = lambda s: s.upper_depletion_mm + s.lower_depletion_mm
    end, season = run_crop(weather, 0, 150, start, crops["maize"], AWC, settings)
    effective_rain = sum(weather.precip[:150])  # 1.5 mm/day is above the effective-rain threshold
    assert total(end) == pytest.approx(total(start) + season.eta_mm - effective_rain, abs=1e-6)


def test_seedling_depends_on_the_topsoil(setup):
    settings, crops = setup
    taw_surface = AWC * 1000 * 0.3
    taw_lower = AWC * 1000 * (settings["profile_depth_m"] - 0.3)
    weather = dry_weather()
    wet_top = SoilState(0.3, 0.0, taw_lower)    # moist topsoil (45 mm usable), dry subsoil
    dry_top = SoilState(0.3, taw_surface, 0.0)  # dry topsoil, moist subsoil (180 mm stored)
    # Roots held at the 0.3 m seedling depth: only the topsoil can supply the crop, although
    # the dry-top profile holds four times more water in total.
    seedling = {**crops["sunflower"], "root_depth_m": [0.3, 0.3]}
    _, wet_season = run_crop(weather, 0, 30, wet_top, seedling, AWC, settings)
    _, dry_season = run_crop(weather, 0, 30, dry_top, seedling, AWC, settings)
    assert dry_season.eta_mm == pytest.approx(0.0)
    assert wet_season.eta_mm > 30


def test_deep_roots_reach_stored_water(setup):
    settings, crops = setup
    taw_surface = AWC * 1000 * 0.3
    weather = dry_weather()
    stored_below = SoilState(0.3, taw_surface, 0.0)   # dry top, full subsoil
    _, maize = run_crop(weather, 0, 150, stored_below, crops["maize"], AWC, settings)
    _, pea = run_crop(weather, 0, 150, stored_below, crops["pea"], AWC, settings)
    # Maize roots (1.35 m) tap more of the stored subsoil water than pea roots (0.8 m).
    assert maize.eta_mm > pea.eta_mm


def test_fallow_dries_the_surface_and_rain_recharges_the_subsoil(setup):
    settings, _ = setup
    start = SoilState(0.3, 0.0, 100.0)
    dried = run_fallow(dry_weather(days=60), 0, 60, start, AWC, settings)
    assert dried.upper_depletion_mm > 0 and dried.lower_depletion_mm == pytest.approx(100.0)
    wet = run_fallow(dry_weather(days=60, et0=0.5, rain=10.0), 0, 60, start, AWC, settings)
    assert wet.upper_depletion_mm == 0 and wet.lower_depletion_mm < 100.0


def test_root_zone_reaches_full_depth_by_mid_season(setup):
    settings, crops = setup
    end, _ = run_crop(dry_weather(rain=2.0), 0, 150, initial_state(AWC, settings), crops["maize"], AWC, settings)
    assert end.upper_depth_m == pytest.approx(sum(crops["maize"]["root_depth_m"]) / 2)
