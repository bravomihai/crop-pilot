"""Internal service. Public farmers use the Next.js endpoint, without accounts."""

import os
import secrets
import uuid
from fastapi import FastAPI, Header, HTTPException, Depends
from .contracts import validate
from .geography import UnsupportedLocationError
from .pipeline import recommend

app = FastAPI(
    title="FieldShift engine",
    docs_url="/docs" if os.getenv("ENABLE_ENGINE_DOCS") == "true" else None,
    redoc_url=None,
)


def authorize(authorization: str | None = Header(default=None)):
    token = os.getenv("INTERNAL_API_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "Internal service token is not configured")
    if not secrets.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(401, "Invalid internal service token")


@app.get("/health")
def health():
    return {
        "service": "fieldshift-engine",
        "contract_version": "1.0",
        "mode": os.getenv("ENGINE_MODE", "demo"),
    }


@app.post("/recommendations", dependencies=[Depends(authorize)])
def recommendations(request: dict, x_request_id: str | None = Header(default=None)):
    errors = validate("recommendation-request", request)
    if errors:
        raise HTTPException(422, {"code": "validation_error", "errors": errors})
    if not any(request["priorities"].values()):
        raise HTTPException(422, "At least one priority must be positive")
    try:
        result = recommend(request, x_request_id or str(uuid.uuid4()))
    except UnsupportedLocationError as error:
        raise HTTPException(422, str(error)) from error
    except NotImplementedError:
        raise HTTPException(
            503, "Scientific engine is not ready; explicitly use demo mode"
        )
    except Exception:
        raise HTTPException(502, "Environmental analysis could not be completed")
    if validate("recommendation-result", result):
        raise HTTPException(500, "Engine output does not match the shared contract")
    return result
