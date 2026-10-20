from fastapi.testclient import TestClient

from src.api.main import app


def test_public_demo_blocks_unrestricted_conversation_listing(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")

    with TestClient(app) as client:
        response = client.get("/api/v1/conversations")

    assert response.status_code == 403, response.text