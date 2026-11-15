"""ISRIC SoilGrids topsoil estimates and derived plant-available water."""

from __future__ import annotations

import math
import os

import httpx

from . import cache

URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
# SoilGrids is often slow; a short timeout keeps the request responsive. A miss is a data gap.
TIMEOUT_SECONDS = float(os.getenv("SOILGRIDS_TIMEOUT_S", "8"))
PROPERTIES = ("clay", "sand", "silt", "phh2o", "soc")
DEPTHS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
SOURCE = {
    "id": "soilgrids",
    "title": "ISRIC SoilGrids 2.0: soil properties, 0–30 cm depth-weighted mean",
    "url": "https://www.isric.org/explore/soilgrids",
    "resolution": "250 m; modelled estimate, not a field analysis",
}
PEDOTRANSFER = {
    "id": "saxton-rawls-2006",
    "title": "Saxton and Rawls (2006), soil water characteristic estimates",
    "url": "https://doi.org/10.2136/sssaj2005.0117",
}


def texture_class(clay: float, sand: float, silt: float) -> str:
    """Group the USDA texture triangle into the contract's four broad classes."""
    if clay >= 35:
        return "clay"
    if sand >= 70 and clay < 15:
        return "sandy"
    if silt >= 50 and clay < 27:
        return "silty"
    return "loamy"


def available_water(
    clay: float, sand: float, organic_carbon_pct: float | None
) -> float:
    """Estimate field capacity minus wilting point, m³/m³ (Saxton and Rawls, 2006)."""
    s, c = sand / 100, clay / 100
    om = min(8.0, (organic_carbon_pct or 1.0) * 1.724)
    t1500 = (
        -0.024 * s
        + 0.487 * c
        + 0.006 * om
        + 0.005 * s * om
        - 0.013 * c * om
        + 0.068 * s * c
        + 0.031
    )
    wilting = t1500 + (0.14 * t1500 - 0.02)
    t33 = (
        -0.251 * s
        + 0.195 * c
        + 0.011 * om
        + 0.006 * s * om
        - 0.027 * c * om
        + 0.452 * s * c
        + 0.299
    )
    capacity = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    return round(max(0.03, min(0.25, capacity - wilting)), 3)


def _mean_0_30(layer: dict) -> float | None:
    factor = (layer.get("unit_measure") or {}).get("d_factor") or 1
    if not isinstance(factor, (int, float)) or factor <= 0:
        return None
    total = weight = 0.0
    for depth in layer.get("depths", []):
        thickness = DEPTHS.get(depth.get("label"))
        raw = (depth.get("values") or {}).get("mean")
        if (
            thickness
            and isinstance(raw, (int, float))
            and not isinstance(raw, bool)
            and math.isfinite(raw)
        ):
            total += raw / factor * thickness
            weight += thickness
    return total / weight if weight else None


def fetch_soil(
    latitude: float, longitude: float
) -> tuple[dict | None, list[dict], list[str]]:
    """Return (soil, sources, data gaps); unavailable soil is a reported gap."""
    params = [("lat", latitude), ("lon", longitude), ("value", "mean")]
    params += [("property", prop) for prop in PROPERTIES]
    params += [("depth", depth) for depth in DEPTHS]
    key = cache.key_for(
        {
            "provider": "soilgrids-v2-0-30",
            "lat": round(latitude, 4),
            "lon": round(longitude, 4),
        }
    )
    payload = cache.read(key)
    if not payload:
        try:
            response = httpx.get(URL, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return None, [], [
                f"SoilGrids was unavailable ({type(error).__name__}); soil properties are unknown."
            ]
        cache.write(key, payload)

    layers = {
        layer.get("name"): layer
        for layer in (payload.get("properties") or {}).get("layers", [])
    }
    raw = {
        name: _mean_0_30(layers[name])
        for name in PROPERTIES
        if name in layers
    }
    soil = {"depth": "0-30 cm", "source": "soilgrids"}
    for name, output, scale in (
        ("clay", "clay_pct", 1.0),
        ("sand", "sand_pct", 1.0),
        ("silt", "silt_pct", 1.0),
        ("phh2o", "ph", 1.0),
        ("soc", "organic_carbon_pct", 0.1),
    ):
        if raw.get(name) is not None:
            soil[output] = round(raw[name] * scale, 2)

    gaps = []
    sources = [SOURCE]
    if all(key in soil for key in ("clay_pct", "sand_pct", "silt_pct")):
        soil["texture"] = texture_class(
            soil["clay_pct"], soil["sand_pct"], soil["silt_pct"]
        )
        soil["awc_m3_m3"] = available_water(
            soil["clay_pct"],
            soil["sand_pct"],
            soil.get("organic_carbon_pct"),
        )
        sources.append(PEDOTRANSFER)
    else:
        gaps.append(
            "SoilGrids returned no complete texture profile for this point; "
            "soil water holding uses the evaluator's fallback."
        )
    if "ph" not in soil:
        gaps.append("SoilGrids returned no pH for this point.")
    if len(soil) <= 2:
        return None, [], gaps or [
            "SoilGrids returned no usable values for this point."
        ]
    return soil, sources, gaps
