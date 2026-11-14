"""Local Docker integration checks. Stops only this project's DB/engine temporarily; restores both.
Run from a configured local checkout: services/engine/.venv/bin/python infra/check-local.py
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]

def compose(*args, **kwargs):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=90, **kwargs)

def main():
    node = shutil.which("node")
    if not node:
        raise SystemExit("Activate Node.js in your shell before running this check")
    values = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line)
    auth = {"Authorization": "Bearer " + values["INTERNAL_API_TOKEN"]}
    fixture = json.loads((ROOT / "packages/contracts/examples/recommendation-request.json").read_text())
    key = "environment:" + hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    cache_url = "http://127.0.0.1:3000/api/internal/cache/" + key
    with httpx.Client(timeout=20, trust_env=False) as client:
        def check(response, status):
            assert response.status_code == status, f"Expected {status}; received {response.status_code}"
            assert response.headers.get("cache-control") == "no-store"
            assert response.headers.get("x-request-id")
            return response

        check(client.get("http://127.0.0.1:8080/api/health"), 200)
        status = check(client.get("http://127.0.0.1:8080/api/engine/status"), 200).json()
        assert status["mode"] == "demo"
        response = check(client.post("http://127.0.0.1:3000/api/recommendations", json=fixture), 200)
        result = response.json()
        assert result["mode"] == "demo" and len(result["plans"]) == 3
        assert result["request_id"] == response.headers["x-request-id"]
        assert result["location"] == fixture["location"]
        assert all(len(plan["steps"]) == 3 for plan in result["plans"])
        print("PASS Docker web -> engine: demo, 3 x 3 crops, same request ID and location")
        assert client.get(cache_url).status_code == 401
        assert client.get("http://127.0.0.1:8080/api/internal/cache/" + key, headers=auth).status_code == 404
        check(client.put(cache_url, headers=auth, json={"public_test": "cache-integration"}), 204)
        assert check(client.get(cache_url, headers=auth), 200).json() == {"public_test": "cache-integration"}
        # The key is generated locally as a fixed namespace + hexadecimal hash.
        sql = 'UPDATE "DataCache" SET "expiresAt" = NOW() - INTERVAL \'1 second\' WHERE "key" = \'' + key + "';"
        compose("exec", "-T", "postgres", "psql", "-U", values.get("POSTGRES_USER", "fieldshift"), "-d", values.get("POSTGRES_DB", "fieldshift"), "-c", sql)
        check(client.get(cache_url, headers=auth), 404)
        cleanup = check(client.delete("http://127.0.0.1:3000/api/internal/cache", headers=auth), 200).json()
        assert cleanup["deleted"] >= 1
        print("PASS internal cache: authenticated write/read, expiry, cleanup; blocked through public gateway")
        geo = check(client.get("http://127.0.0.1:3000/api/locations", params={"q": "Fundulea"}), 200).json()
        assert geo["locations"] and geo["attribution"] == "Open-Meteo / GeoNames"
        print("PASS live geocoding: validated provider data with cache enabled")
        large = client.post("http://127.0.0.1:8080/api/recommendations", json="x" * 40000)
        assert large.status_code == 413 and large.json()["code"] == "request_too_large"
        with ThreadPoolExecutor(max_workers=10) as pool:
            responses = list(pool.map(lambda _: client.post("http://127.0.0.1:8080/api/recommendations", json={}), range(10)))
        limited = [r for r in responses if r.status_code == 429]
        assert limited and all(r.headers.get("retry-after") == "60" for r in limited)
        assert all(r.json()["request_id"] == r.headers["x-request-id"] for r in limited)
        print("PASS public gateway: body-size limit, burst limit, 429 with Retry-After and request ID")
        try:
            compose("stop", "postgres")
            env = os.environ.copy()
            completed = subprocess.run([
                node, "--conditions=react-server", "--env-file=.env.local", "--import", "tsx", "tests/cache-outage.integration.ts",
            ], cwd=ROOT / "apps/web", env=env, capture_output=True, text=True, check=True, timeout=15)
            print(completed.stdout.strip())
            started = time.monotonic()
            check(client.get("http://127.0.0.1:3000/api/locations", params={"q": "Fundulea"}), 200)
            assert time.monotonic() - started < 15
            check(client.post("http://127.0.0.1:3000/api/recommendations", json=fixture), 200)
            check(client.put(cache_url, headers=auth, json={"public_test": "outage"}), 503)
            check(client.delete("http://127.0.0.1:3000/api/internal/cache", headers=auth), 503)
            print("PASS DB stopped: geocoding and demo continue, cache writes/cleanup report 503")
        finally:
            compose("up", "-d", "--wait", "postgres")
        try:
            env = {**os.environ, "ENGINE_MODE": "computed"}
            compose("up", "-d", "--wait", "engine", env=env)
            result = check(client.post("http://127.0.0.1:3000/api/recommendations", json=fixture), 503).json()
            assert result["code"] == "engine_not_ready" and "plans" not in result
            print("PASS real computed boundary: 503, no demo fallback while P2/P3/P4 are unfinished")
        finally:
            compose("up", "-d", "--wait", "engine", env={**os.environ, "ENGINE_MODE": "demo"})
    print("Local DB and engine restored. No farmer requests persisted.")

if __name__ == "__main__":
    main()
