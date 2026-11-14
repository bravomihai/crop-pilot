"""P2: NASA POWER daily adapter. Values keep the provider's parameter names and units."""

from datetime import datetime, timezone
import httpx
from . import cache

PARAMETERS = [
    "T2M",
    "T2M_MIN",
    "T2M_MAX",
    "PRECTOTCORR",
    "RH2M",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
]


def fetch_power(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> dict:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Invalid coordinates")
    if not (1981 <= start_year <= end_year < datetime.now(timezone.utc).year):
        raise ValueError("Use complete historical years since 1981")
    query = {
        "latitude": latitude,
        "longitude": longitude,
        "start": f"{start_year}0101",
        "end": f"{end_year}1231",
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "format": "JSON",
        "time-standard": "UTC",
    }
    key = cache.key_for({"provider": "power-daily-v1", "query": query})
    cached = cache.read(key)
    if cached:
        return cached
    response = httpx.get(
        "https://power.larc.nasa.gov/api/temporal/daily/point", params=query, timeout=60
    )
    response.raise_for_status()
    raw = response.json()
    values = raw["properties"]["parameter"]
    fill = raw.get("header", {}).get("fill_value", -999)
    dates = sorted(set().union(*(set(v) for v in values.values())))
    daily = [
        {
            "date": f"{day[:4]}-{day[4:6]}-{day[6:8]}",
            "values": {
                name: None
                if values.get(name, {}).get(day) in (None, fill)
                else values[name][day]
                for name in PARAMETERS
            },
        }
        for day in dates
    ]
    result = {
        "location": {"latitude": latitude, "longitude": longitude},
        "period": {"start_year": start_year, "end_year": end_year},
        "daily": daily,
        "parameters": raw.get("parameters", {}),
        "sources": [
            {
                "id": "nasa-power",
                "title": "NASA POWER Daily API",
                "url": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
                "resolution": "Regional native provider grid; not a field measurement",
            }
        ],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "data_gaps": [
            "No field-level measurements, soil moisture or soil analysis are supplied by this adapter."
        ],
    }
    cache.write(key, result)
    return result
