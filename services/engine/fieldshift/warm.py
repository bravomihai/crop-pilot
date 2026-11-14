"""Download and cache the public data for demo fields before a presentation.

    cd services/engine
    FIELDSHIFT_CACHE_DIR=cache ENABLE_NASA_POWER=true .venv/bin/python -m fieldshift.warm 44.45,26.5 44.53,25.21

Each point is fetched like a real request (NASA POWER, SoilGrids, SRTM) and stored in the
local cache, so the app answers from cache during the demo. SoilGrids is retried with a
longer timeout here, because a slow answer is fine ahead of time.
"""

from __future__ import annotations

import os
import sys
import time


def main(argv: list[str]) -> int:
    points = []
    for arg in argv:
        try:
            lat, lon = (float(part) for part in arg.split(","))
        except ValueError:
            print(f"Skipping {arg!r}: use latitude,longitude, for example 44.45,26.5")
            continue
        points.append((lat, lon))
    if not points:
        print(__doc__)
        return 2
    if not os.getenv("FIELDSHIFT_CACHE_DIR"):
        print("Set FIELDSHIFT_CACHE_DIR (for example to 'cache') so the results are kept.")
        return 2
    os.environ["ENABLE_NASA_POWER"] = "true"
    os.environ.setdefault("SOILGRIDS_TIMEOUT_S", "60")
    os.environ.setdefault("DATA_DEADLINE_S", "180")  # ahead of time, waiting longer is fine
    from .data_service import build_environment  # after the environment is set

    failures = 0
    for lat, lon in points:
        start = time.time()
        env = build_environment({"location": {"latitude": lat, "longitude": lon}})
        soil = (env.get("static") or {}).get("soil")
        slope = (env.get("static") or {}).get("slope_pct")
        status = "ok" if soil else "soil missing"
        failures += 0 if soil else 1
        print(f"{lat:.4f},{lon:.4f}: {len(env.get('daily', []))} days, soil {'yes' if soil else 'no'}, "
              f"slope {slope}, {time.time() - start:.1f}s ({status})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
