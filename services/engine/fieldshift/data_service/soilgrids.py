"""Optional ISRIC SoilGrids point adapter."""

import httpx

from . import cache

URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ("phh2o", "soc", "clay", "sand", "silt")


def _layer_value(payload: dict, name: str) -> float | None:
    layer = next(
        (item for item in payload["properties"]["layers"] if item["name"] == name),
        None,
    )
    if layer is None:
        return None
    depth = next(
        (item for item in layer["depths"] if item.get("label") == "0-5cm"),
        None,
    )
    if depth is None:
        return None
    raw = depth["values"].get("mean")
    if raw is None:
        return None
    value = float(raw)
    if value == -999:
        return None
    return value / float(layer["unit_measure"]["d_factor"])


def fetch_soilgrids(latitude: float, longitude: float) -> dict:
    """Return topsoil estimates with provider units converted and provenance retained."""
    params = {
        "lat": latitude,
        "lon": longitude,
        "property": list(PROPERTIES),
        "depth": "0-5cm",
        "value": "mean",
    }
    key = cache.key_for({"provider": "soilgrids-v2", "query": params})
    cached = cache.read(key)
    if cached:
        return cached

    response = httpx.get(URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    properties = {}
    ph = _layer_value(payload, "phh2o")
    organic_carbon_g_kg = _layer_value(payload, "soc")
    if ph is not None:
        properties["ph"] = round(ph, 2)
    if organic_carbon_g_kg is not None:
        properties["organic_carbon_pct"] = round(organic_carbon_g_kg / 10, 3)
    for name in ("clay", "sand", "silt"):
        value_g_kg = _layer_value(payload, name)
        if value_g_kg is not None:
            properties[f"{name}_pct"] = round(value_g_kg / 10, 2)

    result = {
        "status": "available" if properties else "unavailable",
        "depth_cm": "0-5",
        "properties": properties,
        "source": {
            "id": "soilgrids",
            "title": "ISRIC SoilGrids 2.0, mean estimates at 0-5 cm",
            "url": URL,
            "resolution": "250 m",
        }
        if properties
        else None,
        "data_gaps": []
        if properties
        else ["SoilGrids returned no usable topsoil values for this point."],
    }
    cache.write(key, result)
    return result
