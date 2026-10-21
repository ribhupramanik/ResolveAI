from fastapi.testclient import TestClient

from src.api.main import app


def test_vercel_origin_can_preflight_chat():
    client = TestClient(app)

    response = client.options(
        "/api/v1/chat",
        headers={
            "Origin": "https://resolve-ai-omega-lime.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://resolve-ai-omega-lime.vercel.app"
    )
