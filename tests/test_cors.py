import pytest
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


@pytest.mark.parametrize(
    "origin,expected_status",
    [
        ("http://localhost:5173", 200),
        ("http://127.0.0.1:5173", 200),
        ("https://untrusted-example.com", 400),
    ],
)
def test_cors_origin_restrictions(origin, expected_status):
    client = TestClient(app)

    response = client.options(
        "/api/v1/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == expected_status

    if expected_status == 200:
        assert response.headers["access-control-allow-origin"] == origin
    else:
        assert "access-control-allow-origin" not in response.headers
