import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import (
    get_pipeline,
)
from src.api.routes import (
    chat,
    health,
)
from src.rag.pipeline import (
    RAGResult,
)
from src.rag.response_validator import (
    ValidationIssue,
)


class FakePipeline:
    def __init__(
        self,
        should_fail: bool = False,
        tool_used: bool = False,
        tool_name: str | None = None,
        tool_success: bool | None = None,
    ):
        self.should_fail = should_fail

        self.tool_used = tool_used
        self.tool_name = tool_name
        self.tool_success = tool_success

    def run(
        self,
        query: str,
        conversation_history=None,
    ) -> RAGResult:

        if self.should_fail:
            raise RuntimeError("Fake pipeline failure.")

        return RAGResult(
            text=("ResolveAI does not have access to live order-tracking information."),
            provider="test-provider",
            model="test-model",
            retrieved_count=5,
            verified_knowledge_count=1,
            verified_knowledge_topics=[
                "order_tracking",
            ],
            system_capability_count=5,
            system_capabilities=[
                "live_operational_data_access",
                "order_lookup",
                "external_action_execution",
                "human_support_routing",
                "verified_support_directory",
            ],

            tool_used=self.tool_used,
            tool_name=self.tool_name,
            tool_success=self.tool_success,
            attempts=2,
            used_fallback=False,
            validation_issues=[
                ValidationIssue(
                    code=("unsupported_support_route_claim"),
                    message=(
                        "Response recommends or "
                        "implies a support route "
                        "that is not verified."
                    ),
                    matched_text=("contact customer support"),
                )
            ],
        )


@pytest.fixture
def app():

    test_app = FastAPI()

    test_app.include_router(
        health.router,
        prefix="/api/v1",
    )

    test_app.include_router(
        chat.router,
        prefix="/api/v1",
    )

    fake_pipeline = FakePipeline()

    test_app.dependency_overrides[get_pipeline] = lambda: fake_pipeline

    return test_app


@pytest.fixture
def client(
    app,
):

    return TestClient(app)


def test_health_endpoint(
    client,
):

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "service": "ResolveAI",
    }


def test_chat_endpoint_returns_pipeline_response(
    client,
):

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "where is my order right now",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == (
        "ResolveAI does not have access to live order-tracking information."
    )

    assert data["metadata"]["retrieved_count"] == 5

    assert data["metadata"]["verified_knowledge_topics"] == ["order_tracking"]

    assert data["metadata"]["attempts"] == 2

    assert data["metadata"]["used_fallback"] is False

    assert data["metadata"]["provider"] == "test-provider"

    assert data["metadata"]["model"] == "test-model"
    assert data["metadata"]["tool_used"] is False
    assert data["metadata"]["tool_name"] is None
    assert data["metadata"]["tool_success"] is None


def test_chat_returns_retry_trigger_issues(
    client,
):

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "where is my order",
        },
    )

    assert response.status_code == 200

    issues = response.json()["metadata"]["retry_trigger_issues"]

    assert len(issues) == 1

    assert issues[0]["code"] == "unsupported_support_route_claim"

    assert issues[0]["matched_text"] == "contact customer support"


def test_empty_chat_message_is_rejected(
    client,
):

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "",
        },
    )

    assert response.status_code == 422


def test_pipeline_failure_returns_500(
    app,
):

    app.dependency_overrides[get_pipeline] = lambda: FakePipeline(should_fail=True)

    client = TestClient(app)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "where is my order",
        },
    )

    assert response.status_code == 500

    assert response.json() == {"detail": ("ResolveAI could not process the request.")}

def test_chat_returns_tool_metadata(
    app,
):
    app.dependency_overrides[get_pipeline] = (
        lambda: FakePipeline(
            tool_used=True,
            tool_name="get_order",
            tool_success=True,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Where is order ORD-10001?",
        },
    )

    assert response.status_code == 200

    metadata = response.json()["metadata"]

    assert metadata["tool_used"] is True
    assert metadata["tool_name"] == "get_order"
    assert metadata["tool_success"] is True

def test_chat_returns_failed_tool_metadata(
    app,
):
    app.dependency_overrides[get_pipeline] = (
        lambda: FakePipeline(
            tool_used=True,
            tool_name="get_order",
            tool_success=False,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Where is order ORD-99999?",
        },
    )

    assert response.status_code == 200

    metadata = response.json()["metadata"]

    assert metadata["tool_used"] is True
    assert metadata["tool_name"] == "get_order"
    assert metadata["tool_success"] is False