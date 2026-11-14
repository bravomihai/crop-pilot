"""Container-side hourly cleanup. No farmer data; secrets are never printed."""
import os
import time
import urllib.request
import urllib.error
import json

base = os.environ.get("CACHE_BACKEND_URL", "http://web:3000").rstrip("/")
while True:
    try:
        for _ in range(100):
            request = urllib.request.Request(
                base + "/api/internal/cache", method="DELETE",
                headers={"Authorization": "Bearer " + os.environ["INTERNAL_API_TOKEN"]},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                result = json.load(response)
            if result["deleted"] < result["batch_size"]:
                break
    except (OSError, ValueError, KeyError):
        print(json.dumps({"event": "cache_maintenance_unavailable"}), flush=True)
    time.sleep(3600)
