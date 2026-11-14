"""P2 owns this interface. Return crop-independent data and source metadata."""

import os
from datetime import datetime, timezone
from .power import fetch_power


def build_environment(request: dict) -> dict:
    if os.getenv("ENABLE_NASA_POWER") != "true":
        raise NotImplementedError(
            "NASA data ingestion is disabled; configure and validate P2 integration"
        )
    years = int(os.getenv("HISTORY_YEARS", "20"))
    if not 1 <= years <= 45:
        raise ValueError("HISTORY_YEARS must be between 1 and 45")
    end = datetime.now(timezone.utc).year - 1
    location = request["location"]
    return fetch_power(
        location["latitude"], location["longitude"], max(1981, end - years + 1), end
    )
