"""HTTP integration boundaries. Computed success uses explicit module stubs, not real science."""
from copy import deepcopy
from fastapi.testclient import TestClient
import pytest
from fieldshift.api import app
from fieldshift import pipeline
from fieldshift.contracts import example

TOKEN = "test-engine-token-with-at-least-32-characters"

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    monkeypatch.setenv("ENGINE_MODE", "demo")
    monkeypatch.setenv("ENABLE_NASA_POWER", "false")
    with TestClient(app) as client:
        yield client

def headers():
    return {"Authorization": "Bearer " + TOKEN, "X-Request-ID": "integration-test-id"}

def test_engine_requires_token(client):
    assert client.post("/recommendations", json=example("recommendation-request")).status_code == 401

def test_demo_preserves_request_id(client):
    response = client.post("/recommendations", headers=headers(), json=example("recommendation-request"))
    assert response.status_code == 200
    assert response.json()["request_id"] == "integration-test-id"
    assert response.json()["mode"] == "demo"

def test_invalid_input_is_rejected(client):
    assert client.post("/recommendations", headers=headers(), json={}).status_code == 422

def test_unimplemented_computed_never_falls_back_to_demo(client, monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "computed")
    response = client.post("/recommendations", headers=headers(), json=example("recommendation-request"))
    assert response.status_code == 503
    assert "plans" not in response.json()

@pytest.mark.parametrize("count,status", [(0, "insufficient_data"), (1, "limited"), (2, "limited"), (3, "complete")])
def test_computed_orchestration_contract_with_module_stubs(client, monkeypatch, count, status):
    monkeypatch.setenv("ENGINE_MODE", "computed")
    fixture = example("recommendation-result")
    monkeypatch.setattr(pipeline, "build_environment", lambda request: {"sources": fixture["sources"], "data_gaps": ["stub data"], "assumptions": []})
    monkeypatch.setattr(pipeline, "load_rules", lambda location: {"sources": []})
    monkeypatch.setattr(pipeline, "recommend_rotations", lambda request, environment, rules, evaluate: deepcopy(fixture["plans"][:count]))
    response = client.post("/recommendations", headers=headers(), json=example("recommendation-request"))
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "computed" and result["status"] == status
    assert len(result["plans"]) == count
    assert result["request_id"] == "integration-test-id"
    assert result["data_gaps"] == ["stub data"]
