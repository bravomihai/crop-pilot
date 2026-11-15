"""Historical satellite land-cover screening; not a current field inspection."""

import math

import httpx

URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/statistics"
SOURCE = {
    "id": "esa-worldcover-2021",
    "title": "ESA WorldCover 2021 via Microsoft Planetary Computer",
    "url": "https://esa-worldcover.org/",
    "resolution": "10 m; 2021 classification",
}
INCOMPATIBLE = {
    10: "tree cover",
    50: "built-up land",
    70: "snow or ice",
    80: "permanent water",
    90: "wetland",
    95: "mangroves",
    100: "moss or lichen",
}
KNOWN_CLASSES = set(INCOMPATIBLE) | {20, 30, 40, 60}
MAX_PIXELS_PER_SIDE = 1024
PIXELS_PER_DEGREE = 12000


def _uncertain(reason: str) -> dict:
    return {
        "status": "uncertain",
        "message": f"Land cover could not be verified: {reason} Check the field before planting.",
    }


def assess_land_cover(boundary: dict | None) -> tuple[dict, list[dict]]:
    if not boundary:
        return _uncertain("no field boundary was provided."), []
    ring = boundary["coordinates"][0]
    west = min(point[0] for point in ring)
    east = max(point[0] for point in ring)
    south = min(point[1] for point in ring)
    north = max(point[1] for point in ring)
    tile_west = math.floor(west / 3) * 3
    tile_south = math.floor(south / 3) * 3
    if east >= tile_west + 3 or north >= tile_south + 3:
        return _uncertain("the field crosses a satellite tile boundary."), []
    if max(east - west, north - south) * PIXELS_PER_DEGREE > MAX_PIXELS_PER_SIDE - 2:
        return _uncertain("the field is too large for full-resolution screening."), []

    item = f"ESA_WorldCover_10m_2021_v200_N{tile_south:02d}E{tile_west:03d}"
    try:
        response = httpx.post(
            URL,
            params={
                "collection": "esa-worldcover",
                "item": item,
                "assets": "map",
                "categorical": "true",
                "max_size": MAX_PIXELS_PER_SIDE,
            },
            json={"type": "Feature", "properties": {}, "geometry": boundary},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return _uncertain(f"the satellite service failed ({type(error).__name__})."), []

    try:
        stats = payload["properties"]["statistics"]["map_b1"]
        counts, classes = stats["histogram"]
        if (
            not isinstance(counts, list)
            or not isinstance(classes, list)
            or len(counts) != len(classes)
            or not counts
            or any(
                isinstance(count, bool)
                or not isinstance(count, (int, float))
                or not math.isfinite(count)
                or count <= 0
                for count in counts
            )
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value not in KNOWN_CLASSES
                for value in classes
            )
            or stats["count"] != sum(counts)
        ):
            raise ValueError("Invalid classification statistics")
    except (KeyError, TypeError, ValueError):
        return _uncertain("the satellite service returned incomplete classification data."), []

    if sum(counts) < 4:
        return _uncertain(
            "the field contains too few 10 m satellite pixels for screening."
        ), [SOURCE.copy()]
    labels = set(classes)
    if len(labels) != 1:
        return {
            "status": "uncertain",
            "message": (
                "The 2021 satellite map shows mixed land cover in this field. "
                "Plans assume cultivable land; check the entire field before planting."
            ),
        }, [SOURCE.copy()]
    value = next(iter(labels))
    if value in INCOMPATIBLE:
        return {
            "status": "incompatible",
            "message": (
                f"The available 2021 satellite pixels in this field show {INCOMPATIBLE[value]}, "
                "so it may not be suitable for planting crops. Verify current conditions "
                "and choose a cultivable field; this is not a legal land-use determination."
            ),
        }, [SOURCE.copy()]
    if value == 40:
        return {
            "status": "cropland",
            "message": (
                "The available 2021 satellite pixels in this field show cropland. Land may have "
                "changed since then; verify current conditions and soil before planting."
            ),
        }, [SOURCE.copy()]
    return {
        "status": "uncertain",
        "message": (
            "The 2021 satellite map does not establish that this field is cultivable. "
            "Plans assume cultivable land; check the field before planting."
        ),
    }, [SOURCE.copy()]
