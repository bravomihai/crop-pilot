"""Cache for public environmental data (NASA POWER, SoilGrids, SRTM).

Two layers, both optional:
- a local disk cache when `FIELDSHIFT_CACHE_DIR` is set (fast, no database; lets a demo
  field be downloaded once in advance with `python -m fieldshift.warm`);
- the shared cache behind the web app's internal API when `CACHE_BACKEND_URL` and
  `INTERNAL_API_TOKEN` are set.

Only public data is cached, never farmer input or results. A failing cache never blocks a
request: it behaves like a miss.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

LOCAL_TTL_SECONDS = 30 * 24 * 3600  # historical data changes rarely


def key_for(value: dict) -> str:
    return (
        "environment:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _local_path(key: str) -> Path | None:
    directory = os.getenv("FIELDSHIFT_CACHE_DIR")
    if not directory:
        return None
    return Path(directory) / (key.split(":", 1)[-1] + ".json")


def _read_local(key: str) -> dict | None:
    path = _local_path(key)
    if path is None or not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime > LOCAL_TTL_SECONDS:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _write_local(key: str, value: dict) -> None:
    path = _local_path(key)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _read_shared(key: str) -> dict | None:
    base = os.getenv("CACHE_BACKEND_URL")
    token = os.getenv("INTERNAL_API_TOKEN")
    if not base or not token:
        return None
    try:
        response = httpx.get(
            f"{base.rstrip('/')}/api/internal/cache/{key}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        return response.json() if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def read(key: str) -> dict | None:
    value = _read_local(key)
    if value is not None:
        return value
    value = _read_shared(key)
    if value is not None:
        _write_local(key, value)
    return value


def write(key: str, value: dict) -> None:
    _write_local(key, value)
    base = os.getenv("CACHE_BACKEND_URL")
    token = os.getenv("INTERNAL_API_TOKEN")
    if not base or not token:
        return
    try:
        httpx.put(
            f"{base.rstrip('/')}/api/internal/cache/{key}",
            headers={"Authorization": f"Bearer {token}"},
            json=value,
            timeout=5,
        )
    except httpx.HTTPError:
        pass
