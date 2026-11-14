"""SRTM point-neighborhood slope from the OpenTopoData elevation API."""

from __future__ import annotations

import math

import httpx

from . import cache

URL = "https://api.opentopodata.org/v1/srtm30m"
ARC_SECOND_DEGREES = 1 / 3600
EARTH_RADIUS_M = 6_371_008.8
SOURCE = {
    "id": "srtm30m-opentopodata",
    "title": "SRTM Global 1 arc-second (SRTMGL1 v003) via OpenTopoData",
    "url": "https://www.opentopodata.org/datasets/srtm/",
    "resolution": "About 30 m; coverage from 60°S to 60°N",
}


def _neighborhood(latitude: float, longitude: float) -> list[tuple[float, float]]:
    return [
        (
            latitude + row * ARC_SECOND_DEGREES,
            longitude + column * ARC_SECOND_DEGREES,
        )
        for row in (1, 0, -1)
        for column in (-1, 0, 1)
    ]


def slope_percent(elevations: list[list[float]], latitude: float) -> float | None:
    """Estimate slope with Horn's 3x3 finite-difference method."""
    if (
        len(elevations) != 3
        or any(len(row) != 3 for row in elevations)
        or not math.isfinite(latitude)
        or not -60 <= latitude <= 60
    ):
        return None
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        for row in elevations
        for value in row
    ):
        return None

    north_west, north, north_east = elevations[0]
    west, _, east = elevations[1]
    south_west, south, south_east = elevations[2]
    spacing_y = math.radians(ARC_SECOND_DEGREES) * EARTH_RADIUS_M
    spacing_x = spacing_y * math.cos(math.radians(latitude))
    dz_dx = (
        north_east + 2 * east + south_east
        - north_west - 2 * west - south_west
    ) / (8 * spacing_x)
    dz_dy = (
        south_west + 2 * south + south_east
        - north_west - 2 * north - north_east
    ) / (8 * spacing_y)
    return round(math.hypot(dz_dx, dz_dy) * 100, 2)


def _unavailable(reason: str) -> tuple[None, list[dict], list[str]]:
    return None, [], [
        f"SRTM slope unavailable ({reason}); erosion risk is not included in the soil score."
    ]


def fetch_slope(
    latitude: float, longitude: float
) -> tuple[float | None, list[dict], list[str]]:
    """Return (slope percent, sources, data gaps) for a 3x3 SRTM neighborhood."""
    if not -60 <= latitude <= 60 or not -180 <= longitude <= 180:
        return _unavailable("the point is outside SRTM coverage")

    points = _neighborhood(latitude, longitude)
    locations = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in points)
    key = cache.key_for(
        {
            "provider": "srtm30m-opentopodata-v1",
            "lat": round(latitude, 6),
            "lon": round(longitude, 6),
        }
    )
    payload = cache.read(key)
    if payload is None:
        try:
            response = httpx.get(
                URL,
                params={"locations": locations, "interpolation": "bilinear"},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return _unavailable(f"the provider request failed ({type(error).__name__})")
        if not isinstance(payload, dict):
            return _unavailable("the provider returned an invalid response")
        if payload.get("status") == "OK" and isinstance(payload.get("results"), list):
            cache.write(key, payload)

    if (
        not isinstance(payload, dict)
        or payload.get("status") != "OK"
        or not isinstance(payload.get("results"), list)
        or len(payload["results"]) != len(points)
    ):
        return _unavailable("the provider returned an incomplete elevation neighborhood")

    results = payload["results"]
    if any(
        not isinstance(result, dict) or result.get("dataset") != "srtm30m"
        for result in results
    ):
        return _unavailable("the provider did not return the requested SRTM30m dataset")
    values = [result.get("elevation") for result in results]
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        for value in values
    ):
        return _unavailable("the provider returned missing elevation samples")

    grid = [values[index : index + 3] for index in range(0, 9, 3)]
    slope = slope_percent(grid, latitude)
    if slope is None:
        return _unavailable("the elevation neighborhood could not be processed")
    return slope, [SOURCE.copy()], []
