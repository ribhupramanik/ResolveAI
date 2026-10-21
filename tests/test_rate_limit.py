from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rate_limit import AIRateLimitMiddleware


def test_ai_endpoints_share_rate_limit():
    app = FastAPI()

    app.add_middleware(
        AIRateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
    )

    @app.post("/api/v1/chat")
    def chat():
        return {"ok": True}

    @app.post("/api/v1/conversations/{conversation_id}/messages")
    def send_message(conversation_id: int):
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    client = TestClient(app)

    first = client.post("/api/v1/chat")
    second = client.post("/api/v1/conversations/1/messages")
    third = client.post("/api/v1/chat")
    health_response = client.get("/api/v1/health")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert int(third.headers["Retry-After"]) > 0
    assert health_response.status_code == 200


def test_ai_rate_limit_resets_after_window():
    app = FastAPI()

    app.add_middleware(
        AIRateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
    )

    @app.post("/api/v1/chat")
    def chat():
        return {"ok": True}

    client = TestClient(app)

    with patch(
        "src.api.rate_limit.monotonic",
        side_effect=[0, 1, 30, 61],
    ):
        response_codes = [client.post("/api/v1/chat").status_code for _ in range(4)]

    assert response_codes == [200, 200, 429, 200]


def test_ai_rate_limit_handles_concurrent_requests():
    app = FastAPI()

    app.add_middleware(
        AIRateLimitMiddleware,
        max_requests=3,
        window_seconds=60,
    )

    @app.post("/api/v1/chat")
    def chat():
        return {"ok": True}

    with TestClient(app) as client:

        def send_request(_):
            return client.post("/api/v1/chat").status_code

        with ThreadPoolExecutor(max_workers=8) as executor:
            status_codes = list(executor.map(send_request, range(20)))

    assert status_codes.count(200) == 3
    assert status_codes.count(429) == 17
