from app.bootstrap.application import create_app
from fastapi.testclient import TestClient


def test_liveness_is_dependency_free() -> None:
    response = TestClient(create_app()).get("/healthz/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "smart-ao-v8",
        "checks": {"process": "ok"},
    }


def test_readiness_without_production_runtime_is_not_ready() -> None:
    response = TestClient(create_app()).get("/healthz/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "smart-ao-v8",
        "checks": {"database": "unknown", "clamav": "unknown"},
    }
