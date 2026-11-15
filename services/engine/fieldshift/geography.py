"""Romania boundary checks for point and field requests."""

import json
import math
from functools import lru_cache
from pathlib import Path

ROMANIA_BOUNDARY_PATH = Path(__file__).resolve().parent / "romania_boundary.geojson"
FIELD_SAMPLE_COUNT = 3


class UnsupportedLocationError(ValueError):
    """Raised when a location or field is outside the supported country."""


@lru_cache(maxsize=1)
def _romania_geometry() -> dict:
    boundary = json.loads(ROMANIA_BOUNDARY_PATH.read_text(encoding="utf-8"))
    for feature in boundary["features"]:
        if feature["properties"].get("shapeGroup") == "ROU":
            return feature["geometry"]
    raise ValueError("The bundled Romania boundary contains no ROU geometry.")


def _point_in_ring(longitude: float, latitude: float, ring: list) -> bool:
    inside = False
    for first, second in zip(ring, ring[1:]):
        x1, y1 = first
        x2, y2 = second
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        if (
            abs(cross) < 1e-10
            and min(x1, x2) <= longitude <= max(x1, x2)
            and min(y1, y2) <= latitude <= max(y1, y2)
        ):
            return True
        if (y1 > latitude) != (y2 > latitude):
            crossing_longitude = x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
            if longitude < crossing_longitude:
                inside = not inside
    return inside


def _point_in_romania(longitude: float, latitude: float) -> bool:
    geometry = _romania_geometry()
    polygons = (
        geometry["coordinates"]
        if geometry["type"] == "MultiPolygon"
        else [geometry["coordinates"]]
    )
    return any(
        _point_in_ring(longitude, latitude, polygon[0])
        and not any(
            _point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
        )
        for polygon in polygons
    )


def validate_location(location: dict) -> None:
    if not _point_in_romania(location["longitude"], location["latitude"]):
        raise UnsupportedLocationError(
            "The computed crop-screening model currently supports locations inside Romania."
        )


def validate_field_boundary(field_boundary: dict, location: dict | None = None) -> None:
    ring = field_boundary["coordinates"][0]
    if (
        len(ring) < 4
        or ring[0] != ring[-1]
        or len({tuple(point) for point in ring[:-1]}) < 3
    ):
        raise UnsupportedLocationError(
            "A field boundary must be a closed polygon with at least three distinct points."
        )

    area = sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(ring, ring[1:])
    )
    if abs(area) < 1e-10:
        raise UnsupportedLocationError("The field boundary must enclose an area.")
    if location and not _point_in_ring(
        location["longitude"], location["latitude"], ring
    ):
        raise UnsupportedLocationError(
            "The representative location must be inside the field boundary."
        )

    sample_count = 0
    for first, second in zip(ring, ring[1:]):
        steps = max(
            1,
            math.ceil(
                max(abs(second[0] - first[0]), abs(second[1] - first[1])) * 100
            ),
        )
        sample_count += steps
        if sample_count > 20000:
            raise UnsupportedLocationError(
                "The field boundary is too large to validate as a Romanian field."
            )
        for step in range(steps + 1):
            fraction = step / steps
            longitude = first[0] + (second[0] - first[0]) * fraction
            latitude = first[1] + (second[1] - first[1]) * fraction
            if not _point_in_romania(longitude, latitude):
                raise UnsupportedLocationError(
                    "The entire field boundary must be inside Romania."
                )


def field_sample_points(field_boundary: dict, location: dict) -> list[dict]:
    """Choose up to three deterministic, spread-out locations inside a field."""
    ring = field_boundary["coordinates"][0]
    representative = (location["longitude"], location["latitude"])
    candidates = {}

    def add_candidate(longitude: float, latitude: float) -> None:
        point = (longitude, latitude)
        if _point_in_ring(longitude, latitude, ring):
            candidates[(round(longitude, 7), round(latitude, 7))] = point

    add_candidate(*representative)
    longitudes = [point[0] for point in ring[:-1]]
    latitudes = [point[1] for point in ring[:-1]]
    min_longitude, max_longitude = min(longitudes), max(longitudes)
    min_latitude, max_latitude = min(latitudes), max(latitudes)
    for row in range(5):
        latitude = min_latitude + (row + 0.5) * (max_latitude - min_latitude) / 5
        for column in range(5):
            longitude = min_longitude + (column + 0.5) * (
                max_longitude - min_longitude
            ) / 5
            add_candidate(longitude, latitude)
    for first, second in zip(ring, ring[1:]):
        add_candidate(
            (first[0] + second[0]) / 2,
            (first[1] + second[1]) / 2,
        )
    for longitude, latitude in ring[:-1]:
        add_candidate(longitude, latitude)

    selected = [representative]
    candidates.pop(
        (round(representative[0], 7), round(representative[1], 7)), None
    )
    while candidates and len(selected) < FIELD_SAMPLE_COUNT:
        latitude_scale = math.cos(math.radians(location["latitude"]))

        def distance_to_nearest(point: tuple[float, float]) -> float:
            longitude, latitude = point
            return min(
                ((longitude - chosen[0]) * latitude_scale) ** 2
                + (latitude - chosen[1]) ** 2
                for chosen in selected
            )

        key, point = max(
            candidates.items(), key=lambda item: distance_to_nearest(item[1])
        )
        selected.append(point)
        del candidates[key]

    return [
        {"latitude": latitude, "longitude": longitude}
        for longitude, latitude in selected
    ]
