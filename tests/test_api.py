from fastapi.testclient import TestClient

from hsmt_engine.api import create_app


def test_health_and_auth(settings):
    with TestClient(create_app(settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["exa_configured"] is False
        denied = client.get("/v1/jobs/missing")
        assert denied.status_code == 401
        missing = client.get(
            "/v1/jobs/missing", headers={"Authorization": "Bearer test-token"}
        )
        assert missing.status_code == 404
