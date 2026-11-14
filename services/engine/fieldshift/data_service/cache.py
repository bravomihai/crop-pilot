"""Optional HTTP cache for public environmental data; credentials stay server-side."""

import os
import hashlib
import json
import httpx


def key_for(value: dict) -> str:
    return (
        "environment:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def read(key: str) -> dict | None:
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


def write(key: str, value: dict) -> None:
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
