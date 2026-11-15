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


def _cache_key(latitude: float, longitude: float) -> str:
    return cache.key_for(
        {
            "provider": "srtm30m-opentopodata-v1",
            "lat": round(latitude, 6),
            "lon": round(longitude, 6),
        }
    )


def _payload_slope(payload: dict, latitude: float) -> tuple[float | None, str | None]:
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "OK"
        or not isinstance(payload.get("results"), list)
        or len(payload["results"]) != 9
    ):
        return None, "the provider returned an incomplete elevation neighborhood"
    results = payload["results"]
    if any(
        not isinstance(result, dict) or result.get("dataset") != "srtm30m"
        for result in results
    ):
        return None, "the provider did not return the requested SRTM30m dataset"
    values = [result.get("elevation") for result in results]
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        for value in values
    ):
        return None, "the provider returned missing elevation samples"
    grid = [values[index : index + 3] for index in range(0, 9, 3)]
    slope = slope_percent(grid, latitude)
    if slope is None:
        return None, "the elevation neighborhood could not be processed"
    return slope, None


def fetch_slopes(
    locations: list[tuple[float, float]],
) -> tuple[list[float | None], list[dict], list[str]]:
    """Fetch slope estimates for multiple points in one provider request."""
    slopes: list[float | None] = [None] * len(locations)
    gaps: list[str] = []
    pending = []
    for index, (latitude, longitude) in enumerate(locations):
        if not -60 <= latitude <= 60 or not -180 <= longitude <= 180:
            gaps.append(
                f"SRTM slope unavailable at sample {index + 1} "
                "(the point is outside SRTM coverage); erosion risk is not "
                "included in the soil score."
            )
            continue
        key = _cache_key(latitude, longitude)
        cached = cache.read(key)
        if cached is not None:
            slope, _ = _payload_slope(cached, latitude)
            if slope is not None:
                slopes[index] = slope
                continue
        pending.append((index, latitude, longitude, key))

    if pending:
        neighborhoods = [
            _neighborhood(latitude, longitude)
            for _, latitude, longitude, _ in pending
        ]
        locations_query = "|".join(
            f"{latitude:.6f},{longitude:.6f}"
            for neighborhood in neighborhoods
            for latitude, longitude in neighborhood
        )
        try:
            response = httpx.get(
                URL,
                params={"locations": locations_query, "interpolation": "bilinear"},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            payload = None
            request_error = f"the provider request failed ({type(error).__name__})"
        else:
            request_error = None

        results = payload.get("results") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("status") != "OK"
            or not isinstance(results, list)
            or len(results) != 9 * len(pending)
        ):
            request_error = request_error or (
                "the provider returned an incomplete elevation response"
            )
            for index, _, _, _ in pending:
                gaps.append(
                    f"SRTM slope unavailable at sample {index + 1} ({request_error}); "
                    "erosion risk is not included in the soil score."
                )
        else:
            for offset, (index, latitude, _, key) in enumerate(pending):
                result_payload = {
                    "status": "OK",
                    "results": results[offset * 9 : (offset + 1) * 9],
                }
                slope, error = _payload_slope(result_payload, latitude)
                if error:
                    gaps.append(
                        f"SRTM slope unavailable at sample {index + 1} ({error}); "
                        "erosion risk is not included in the soil score."
                    )
                    continue
                slopes[index] = slope
                cache.write(key, result_payload)

    sources = [SOURCE.copy()] if any(slope is not None for slope in slopes) else []
    return slopes, sources, gaps


def fetch_slope(
    latitude: float, longitude: float
) -> tuple[float | None, list[dict], list[str]]:
    """Return (slope percent, sources, data gaps) for a 3x3 SRTM neighborhood."""
    slopes, sources, gaps = fetch_slopes([(latitude, longitude)])
    return slopes[0], sources, gaps
