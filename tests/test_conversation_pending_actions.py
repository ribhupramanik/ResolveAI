import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import (
    get_db,
    get_pipeline,
)
from src.api.routes import conversations
from src.db.database import SessionLocal
from src.db.models import Conversation
from src.rag.pipeline import RAGResult
from src.services.pending_action_service import (
    PendingActionService,
)


class CountingFakePipeline:
    def __init__(
        self,
        *,
        tool_used=False,
        tool_name=None,
        tool_success=None,
        tool_data=None,
        used_fallback=False,
    ):
        self.run_calls = 0

        self.tool_used = tool_used
        self.tool_name = tool_name
        self.tool_success = tool_success
        self.tool_data = tool_data
        self.used_fallback = used_fallback

    def run(
        self,
        query: str,
        conversation_history=None,
    ) -> RAGResult:
        self.run_calls += 1

        return RAGResult(
            text="Normal pipeline response.",
            provider="test-provider",
            model="test-model",
            retrieved_count=0,
            verified_knowledge_count=0,
            verified_knowledge_topics=[],
            system_capability_count=0,
            system_capabilities=[],
            attempts=1,
            used_fallback=self.used_fallback,
            validation_issues=[],
            tool_used=self.tool_used,
            tool_name=self.tool_name,
            tool_success=self.tool_success,
            tool_data=self.tool_data,
        )


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def fake_pipeline():
    return CountingFakePipeline()


@pytest.fixture
def app(
    db,
    fake_pipeline,
):
    test_app = FastAPI()

    test_app.include_router(
        conversations.router,
        prefix="/api/v1",
    )

    def override_db():
        yield db

    test_app.dependency_overrides[get_db] = override_db

    test_app.dependency_overrides[get_pipeline] = lambda: fake_pipeline

    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def conversation(db):
    conversation = Conversation(
        title="Pending API test",
    )

    db.add(conversation)
    db.flush()

    return conversation


def create_pending_cancellation(
    db,
    conversation,
):
    service = PendingActionService(db)

    return service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10002",
        action_data={
            "order_status": "processing",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )


def test_yes_confirms_pending_action_without_pipeline(
    client,
    db,
    conversation,
    fake_pipeline,
):
    action = create_pending_cancellation(
        db,
        conversation,
    )

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "yes",
        },
    )

    assert response.status_code == 201

    db.refresh(action)

    assert action.status == "confirmed"
    assert action.confirmed_at is not None

    assert action.action_data["action_performed"] is False

    assert fake_pipeline.run_calls == 0

    data = response.json()

    assert data["assistant_message"]["content"] == (
        "Cancellation of ORD-10002 "
        "has been confirmed. "
        "No cancellation has been performed yet."
    )
    assert data["pending_action"] is None


def test_no_rejects_pending_action_without_pipeline(
    client,
    db,
    conversation,
    fake_pipeline,
):
    action = create_pending_cancellation(
        db,
        conversation,
    )

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "no",
        },
    )

    assert response.status_code == 201

    db.refresh(action)

    assert action.status == "rejected"
    assert action.confirmed_at is None

    assert action.action_data["action_performed"] is False

    assert fake_pipeline.run_calls == 0

    data = response.json()

    assert data["assistant_message"]["content"] == (
        "The pending cancellation request for "
        "ORD-10002 has been rejected. "
        "No cancellation has been performed."
    )
    assert data["pending_action"] is None


def test_yes_without_pending_action_uses_pipeline(
    client,
    conversation,
    fake_pipeline,
):
    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "yes",
        },
    )

    assert response.status_code == 201

    assert fake_pipeline.run_calls == 1

    data = response.json()

    assert data["assistant_message"]["content"] == "Normal pipeline response."
    assert data["pending_action"] is None


def test_unrelated_message_leaves_action_pending(
    client,
    db,
    conversation,
    fake_pipeline,
):
    action = create_pending_cancellation(
        db,
        conversation,
    )

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "What is my order status?",
        },
    )

    assert response.status_code == 201

    db.refresh(action)

    assert action.status == "pending"
    assert action.confirmed_at is None

    assert fake_pipeline.run_calls == 1

    data = response.json()

    assert data["pending_action"] == {
        "id": action.id,
        "action_type": "cancel_order",
        "target_identifier": "ORD-10002",
        "status": "pending",
    }


def test_get_pending_action_returns_safe_ui_state(
    client,
    db,
    conversation,
):
    action = create_pending_cancellation(
        db,
        conversation,
    )

    response = client.get(
        (  # noqa: UP034
            f"/api/v1/conversations/{conversation.id}/pending-action"
        )
    )

    assert response.status_code == 200

    assert response.json() == {
        "id": action.id,
        "action_type": "cancel_order",
        "target_identifier": "ORD-10002",
        "status": "pending",
    }


def test_get_pending_action_returns_null_when_none_exists(
    client,
    conversation,
):
    response = client.get(
        (  # noqa: UP034
            f"/api/v1/conversations/{conversation.id}/pending-action"
        )
    )

    assert response.status_code == 200
    assert response.json() is None


def test_get_pending_action_disappears_after_confirmation(
    client,
    db,
    conversation,
):
    create_pending_cancellation(
        db,
        conversation,
    )

    service = PendingActionService(db)

    confirmed = service.confirm_pending_action(conversation.id)

    assert confirmed is not None
    assert confirmed.status == "confirmed"

    response = client.get(
        (  # noqa: UP034
            f"/api/v1/conversations/{conversation.id}/pending-action"
        )
    )

    assert response.status_code == 200
    assert response.json() is None


def test_get_pending_action_disappears_after_rejection(
    client,
    db,
    conversation,
):
    create_pending_cancellation(
        db,
        conversation,
    )

    service = PendingActionService(db)

    rejected = service.reject_pending_action(conversation.id)

    assert rejected is not None
    assert rejected.status == "rejected"

    response = client.get(f"/api/v1/conversations/{conversation.id}/pending-action")

    assert response.status_code == 200
    assert response.json() is None


def test_eligible_cancellation_returns_pending_action(
    app,
    db,
    conversation,
):
    cancellation_pipeline = CountingFakePipeline(
        tool_used=True,
        tool_name="check_cancellation_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "eligible": True,
            "reason": (
                "The order is still processing and is eligible for cancellation."
            ),
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    app.dependency_overrides[get_pipeline] = lambda: cancellation_pipeline

    client = TestClient(app)

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "Can I cancel ORD-10002?",
        },
    )

    assert response.status_code == 201

    assert cancellation_pipeline.run_calls == 1

    data = response.json()

    pending = data["pending_action"]

    assert pending is not None

    assert pending["action_type"] == "cancel_order"

    assert pending["target_identifier"] == "ORD-10002"

    assert pending["status"] == "pending"

    service = PendingActionService(db)

    stored_action = service.get_pending_action(conversation.id)

    assert stored_action is not None

    assert stored_action.id == pending["id"]

    assert stored_action.target_identifier == "ORD-10002"

    assert stored_action.status == "pending"

    assert stored_action.action_data["action_performed"] is False


def test_ineligible_cancellation_returns_no_pending_action(
    app,
    db,
    conversation,
):
    cancellation_pipeline = CountingFakePipeline(
        tool_used=True,
        tool_name="check_cancellation_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10001",
            "status": "shipped",
            "eligible": False,
            "reason": ("The order has already shipped."),
            "requires_confirmation": False,
            "action_performed": False,
        },
    )

    app.dependency_overrides[get_pipeline] = lambda: cancellation_pipeline

    client = TestClient(app)

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "Can I cancel ORD-10001?",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["pending_action"] is None

    service = PendingActionService(db)

    assert service.get_pending_action(conversation.id) is None
