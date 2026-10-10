from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from src.api.dependencies import (
    get_db,
    get_pipeline,
)
from src.api.routes import conversations
from src.db.database import SessionLocal
from src.db.models import (
    ActionExecutionAudit,
    Conversation,
    Customer,
    Order,
    PendingAction,
    Refund,
)
from src.rag.pipeline import RAGResult
from src.services.pending_action_service import (
    PendingActionService,
)
from src.tools.base import ToolResult


class CountingFakePipeline:
    def __init__(
        self,
        *,
        tool_used=False,
        tool_name=None,
        tool_success=None,
        tool_data=None,
        tool_results=(),
        used_fallback=False,
    ):
        self.run_calls = 0

        self.tool_used = tool_used
        self.tool_name = tool_name
        self.tool_success = tool_success
        self.tool_data = tool_data
        self.used_fallback = used_fallback
        self.tool_results = tool_results

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
            tool_results=self.tool_results,
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


def test_yes_executes_pending_cancellation_without_pipeline(
    client,
    db,
    execution_case_factory,
    fake_pipeline,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    assert order.status == "processing"
    assert action.status == "pending"

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": "yes",
        },
    )

    assert response.status_code == 201

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert fake_pipeline.run_calls == 0

    assert stored_order is not None
    assert stored_order.status == "cancelled"

    assert stored_action is not None
    assert stored_action.status == "executed"
    assert stored_action.confirmed_at is not None

    assert stored_action.action_data["action_performed"] is True

    assert audit is not None
    assert audit.outcome == "executed"
    assert audit.action_performed is True

    data = response.json()

    assert data["assistant_message"]["content"] == (
        f"Order {order.order_number} has been cancelled successfully."
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


@pytest.fixture
def execution_case_factory(db):
    created_cases = []

    def create_case(
        *,
        action_status: str = "confirmed",
        order_status: str = "processing",
    ):
        token = uuid4().hex[:10].upper()

        numeric_suffix = str(uuid4().int % 10_000_000_000).zfill(10)

        customer = Customer(
            customer_code=f"CUST-API-{token}",
            name=f"Execution API Test {token}",
            email=(f"execution-api-{token.lower()}@example.com"),
        )

        db.add(customer)
        db.flush()

        order = Order(
            order_number=f"ORD-{numeric_suffix}",
            customer_id=customer.id,
            status=order_status,
            payment_status="paid",
            total_amount=Decimal("999.00"),
            currency="INR",
            shipping_address="API test address",
        )

        db.add(order)
        db.flush()

        conversation = Conversation(
            title="Execution API test",
        )

        db.add(conversation)
        db.flush()

        service = PendingActionService(db)

        action = service.create_pending_action(
            conversation_id=conversation.id,
            action_type="cancel_order",
            target_type="order",
            target_identifier=order.order_number,
            action_data={
                "order_status": order_status,
                "eligible": True,
                "requires_confirmation": True,
                "action_performed": False,
            },
        )

        if action_status == "confirmed":
            confirmed = service.confirm_pending_action(conversation.id)

            assert confirmed is not None

        elif action_status == "rejected":
            rejected = service.reject_pending_action(conversation.id)

            assert rejected is not None

        elif action_status != "pending":
            raise ValueError("Unsupported action status.")

        # Important: the endpoint owns its own
        # transaction and may commit or rollback.
        # Therefore setup must already be committed.
        db.commit()

        db.refresh(customer)
        db.refresh(order)
        db.refresh(conversation)
        db.refresh(action)

        case = {
            "customer": customer,
            "order": order,
            "conversation": conversation,
            "action": action,
        }

        created_cases.append(
            {
                "customer_id": customer.id,
                "order_id": order.id,
                "conversation_id": conversation.id,
                "action_id": action.id,
            }
        )

        return case

    yield create_case

    # The execution endpoint can commit, so normal
    # fixture rollback cannot clean these records.
    db.rollback()

    cleanup_db = SessionLocal()

    try:
        for case in reversed(created_cases):
            cleanup_db.execute(
                delete(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == case["action_id"]
                )
            )

            cleanup_db.execute(
                delete(PendingAction).where(PendingAction.id == case["action_id"])
            )

            cleanup_db.execute(delete(Order).where(Order.id == case["order_id"]))

            cleanup_db.execute(
                delete(Conversation).where(Conversation.id == case["conversation_id"])
            )

            cleanup_db.execute(
                delete(Customer).where(Customer.id == case["customer_id"])
            )

        cleanup_db.commit()

    except Exception:
        cleanup_db.rollback()
        raise

    finally:
        cleanup_db.close()


def test_execute_confirmed_cancellation_via_api(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory()

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/execute"
    )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "action_id": action.id,
        "success": True,
        "executed": True,
        "already_executed": False,
        "action_status": "executed",
        "order_number": order.order_number,
        "order_status": "cancelled",
        "reason": ("Order cancellation executed successfully."),
    }

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order is not None
    assert stored_order.status == "cancelled"

    assert stored_action is not None
    assert stored_action.status == "executed"

    assert audit is not None
    assert audit.outcome == "executed"
    assert audit.action_performed is True


def test_execute_pending_cancellation_is_rejected(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/execute"
    )

    assert response.status_code == 409

    assert response.json() == {"detail": ("Cancellation has not been confirmed.")}

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order.status == "processing"
    assert stored_action.status == "pending"
    assert audit is None


def test_execute_rejected_cancellation_is_rejected(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="rejected",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/execute"
    )

    assert response.status_code == 409

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order.status == "processing"
    assert stored_action.status == "rejected"
    assert audit is None


def test_action_cannot_execute_from_another_conversation(
    client,
    db,
    execution_case_factory,
):
    first = execution_case_factory()
    second = execution_case_factory()

    action = first["action"]
    order = first["order"]

    wrong_conversation = second["conversation"]

    response = client.post(
        (  # noqa: UP034
            f"/api/v1/conversations/"
            f"{wrong_conversation.id}/"
            f"pending-actions/"
            f"{action.id}/execute"
        )
    )

    assert response.status_code == 404

    assert response.json() == {"detail": "Pending action not found."}

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    assert stored_order.status == "processing"
    assert stored_action.status == "confirmed"


def test_execute_cancellation_invalidates_if_order_shipped(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory()

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    # Simulate fulfilment changing the order
    # after confirmation but before execution.
    order.status = "shipped"
    db.commit()

    response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/execute"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False
    assert data["executed"] is False
    assert data["already_executed"] is False

    assert data["action_status"] == "invalidated"
    assert data["order_status"] == "shipped"

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order.status == "shipped"

    assert stored_action.status == "invalidated"

    assert audit is not None
    assert audit.outcome == "invalidated"
    assert audit.action_performed is False

    assert audit.previous_target_status == "shipped"

    assert audit.final_target_status == "shipped"


def test_execute_cancellation_endpoint_is_idempotent(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory()

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    url = f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/execute"

    first_response = client.post(url)

    second_response = client.post(url)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first = first_response.json()
    second = second_response.json()

    assert first["success"] is True
    assert first["executed"] is True
    assert first["already_executed"] is False

    assert second["success"] is True
    assert second["executed"] is False
    assert second["already_executed"] is True

    assert first["order_status"] == "cancelled"
    assert second["order_status"] == "cancelled"

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    audits = db.scalars(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    ).all()

    assert stored_order.status == "cancelled"

    assert len(audits) == 1
    assert audits[0].outcome == "executed"


def test_confirm_and_execute_pending_cancellation_via_api(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    assert action.status == "pending"
    assert action.confirmed_at is None
    assert order.status == "processing"

    response = client.post(
        f"/api/v1/conversations/"
        f"{conversation.id}/pending-actions/"
        f"{action.id}/confirm-and-execute"
    )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "action_id": action.id,
        "success": True,
        "executed": True,
        "already_executed": False,
        "action_status": "executed",
        "order_number": order.order_number,
        "order_status": "cancelled",
        "reason": ("Order cancellation executed successfully."),
    }

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order is not None
    assert stored_order.status == "cancelled"

    assert stored_action is not None
    assert stored_action.status == "executed"
    assert stored_action.confirmed_at is not None
    assert stored_action.action_data["action_performed"] is True

    assert audit is not None
    assert audit.outcome == "executed"
    assert audit.action_performed is True
    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]

    assert len(assistant_messages) == 1

    assert assistant_messages[0]["content"] == (
        f"Order {order.order_number} has been cancelled successfully."
    )


def test_confirm_and_execute_endpoint_is_idempotent(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    url = (
        f"/api/v1/conversations/"
        f"{conversation.id}/pending-actions/"
        f"{action.id}/confirm-and-execute"
    )

    first_response = client.post(url)
    second_response = client.post(url)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first = first_response.json()
    second = second_response.json()

    assert first["success"] is True
    assert first["executed"] is True
    assert first["already_executed"] is False

    assert second["success"] is True
    assert second["executed"] is False
    assert second["already_executed"] is True

    assert first["action_status"] == "executed"
    assert second["action_status"] == "executed"

    assert first["order_status"] == "cancelled"
    assert second["order_status"] == "cancelled"

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audits = db.scalars(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    ).all()

    assert stored_order.status == "cancelled"
    assert stored_action.status == "executed"

    assert len(audits) == 1
    assert audits[0].outcome == "executed"
    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    success_messages = [
        message
        for message in messages
        if (
            message["role"] == "assistant"
            and message["content"]
            == (f"Order {order.order_number} has been cancelled successfully.")
        )
    ]

    assert len(success_messages) == 1


def test_confirm_and_execute_invalidates_if_order_shipped(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    # Eligibility was originally checked while
    # the order was processing.
    #
    # Simulate fulfilment shipping the order before
    # the customer clicks Confirm cancellation.
    order.status = "shipped"
    db.commit()

    response = client.post(
        f"/api/v1/conversations/"
        f"{conversation.id}/pending-actions/"
        f"{action.id}/confirm-and-execute"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False
    assert data["executed"] is False
    assert data["already_executed"] is False

    assert data["action_status"] == "invalidated"
    assert data["order_status"] == "shipped"

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order is not None
    assert stored_order.status == "shipped"

    assert stored_action is not None
    assert stored_action.status == "invalidated"

    # The customer really did confirm, even though
    # execution was blocked by the latest order state.
    assert stored_action.confirmed_at is not None

    assert stored_action.action_data["action_performed"] is False

    assert audit is not None
    assert audit.outcome == "invalidated"
    assert audit.action_performed is False

    assert audit.previous_target_status == "shipped"
    assert audit.final_target_status == "shipped"
    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]

    assert len(assistant_messages) == 1

    assert assistant_messages[0]["content"].startswith(
        f"The cancellation for {order.order_number} could not be completed."
    )


def test_confirm_and_execute_rejected_action_is_rejected(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="rejected",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    response = client.post(
        f"/api/v1/conversations/"
        f"{conversation.id}/pending-actions/"
        f"{action.id}/confirm-and-execute"
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": ("Cancellation cannot be confirmed because the action is 'rejected'.")
    }

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order is not None
    assert stored_order.status == "processing"

    assert stored_action is not None
    assert stored_action.status == "rejected"

    assert audit is None


def test_confirm_and_execute_cannot_use_another_conversation(
    client,
    db,
    execution_case_factory,
):
    first = execution_case_factory(
        action_status="pending",
    )

    second = execution_case_factory(
        action_status="pending",
    )

    action = first["action"]
    order = first["order"]

    wrong_conversation = second["conversation"]

    response = client.post(
        f"/api/v1/conversations/"
        f"{wrong_conversation.id}/pending-actions/"
        f"{action.id}/confirm-and-execute"
    )

    assert response.status_code == 404

    assert response.json() == {"detail": "Pending action not found."}

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    assert stored_order.status == "processing"
    assert stored_action.status == "pending"
    assert stored_action.confirmed_at is None


def test_reject_pending_action_via_exact_id(
    client,
    db,
    execution_case_factory,
    fake_pipeline,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/reject"
    )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "id": action.id,
        "action_type": "cancel_order",
        "target_identifier": order.order_number,
        "status": "rejected",
    }

    assert fake_pipeline.run_calls == 0

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert stored_order is not None
    assert stored_order.status == "processing"

    assert stored_action is not None
    assert stored_action.status == "rejected"
    assert stored_action.confirmed_at is None

    assert stored_action.action_data["action_performed"] is False

    assert audit is None

    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assert len(messages) == 1

    assert messages[0]["role"] == "assistant"

    assert messages[0]["content"] == (
        f"The pending cancellation request for "
        f"{order.order_number} has been rejected. "
        f"No cancellation has been performed."
    )


def test_reject_action_cannot_use_another_conversation(
    client,
    db,
    execution_case_factory,
):
    first = execution_case_factory(
        action_status="pending",
    )

    second = execution_case_factory(
        action_status="pending",
    )

    action = first["action"]
    order = first["order"]

    wrong_conversation = second["conversation"]

    response = client.post(
        f"/api/v1/conversations/"
        f"{wrong_conversation.id}/"
        f"pending-actions/"
        f"{action.id}/reject"
    )

    assert response.status_code == 404

    assert response.json() == {"detail": "Pending action not found."}

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    assert stored_order is not None
    assert stored_order.status == "processing"

    assert stored_action is not None
    assert stored_action.status == "pending"


def test_reject_pending_action_endpoint_is_idempotent(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    url = f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/reject"

    first_response = client.post(url)
    second_response = client.post(url)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json()["status"] == "rejected"
    assert second_response.json()["status"] == "rejected"

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    assert stored_order is not None
    assert stored_order.status == "processing"

    assert stored_action is not None
    assert stored_action.status == "rejected"

    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    rejection_messages = [
        message
        for message in messages
        if (
            message["role"] == "assistant"
            and message["content"]
            == (
                f"The pending cancellation request for "
                f"{order.order_number} has been rejected. "
                f"No cancellation has been performed."
            )
        )
    ]

    assert len(rejection_messages) == 1


def test_executed_action_cannot_be_rejected(
    client,
    db,
    execution_case_factory,
):
    case = execution_case_factory(
        action_status="confirmed",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    execute_response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/execute"
    )

    assert execute_response.status_code == 200

    reject_response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action.id}/reject"
    )

    assert reject_response.status_code == 409

    db.expire_all()

    stored_order = db.get(
        Order,
        order.id,
    )

    stored_action = db.get(
        PendingAction,
        action.id,
    )

    assert stored_order is not None
    assert stored_order.status == "cancelled"

    assert stored_action is not None
    assert stored_action.status == "executed"


def test_multi_tool_executions_are_returned_and_persisted(
    app,
    client,
    conversation,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
                "customer_name": "Meera Sen",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=True,
            data={
                "order_number": "ORD-10003",
                "refund_number": "REF-10003",
                "status": "processing",
                "amount": "3899.00",
                "currency": "INR",
            },
        ),
    )

    multi_tool_pipeline = CountingFakePipeline(
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_data=None,
        tool_results=tool_results,
    )

    app.dependency_overrides[get_pipeline] = lambda: multi_tool_pipeline

    response = client.post(
        (f"/api/v1/conversations/{conversation.id}/messages"),
        json={
            "message": ("What is the order status and refund status for ORD-10003?"),
        },
    )

    assert response.status_code == 201

    data = response.json()

    expected_tool_executions = [
        {
            "tool_name": "get_order",
            "success": True,
        },
        {
            "tool_name": "get_refund_status",
            "success": True,
        },
    ]

    # Public response metadata should contain only
    # the safe execution summary.
    assert data["metadata"]["tool_executions"] == expected_tool_executions

    # The same safe metadata must be persisted on
    # the assistant message.
    assert (
        data["assistant_message"]["ai_metadata"]["tool_executions"]
        == expected_tool_executions
    )

    # Reload from the API to prove this survives
    # persistence rather than only existing in the
    # immediate POST response.
    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]

    assert len(assistant_messages) == 1

    persisted_metadata = assistant_messages[0]["ai_metadata"]

    assert persisted_metadata["tool_executions"] == expected_tool_executions

    # Raw operational data must not be copied into
    # the public/persisted tool execution summary.
    for execution in persisted_metadata["tool_executions"]:
        assert set(execution) == {
            "tool_name",
            "success",
        }


def test_chat_refund_confirmation_does_not_execute_cancellation(
    client,
    db,
    execution_case_factory,
    fake_pipeline,
    monkeypatch,
):
    # Create a real test order, conversation,
    # and pending action in resolveai_test.
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    order_id = order.id
    action_id = action.id

    # Convert the test PendingAction into
    # a refund initiation request.
    action.action_type = "initiate_refund"

    action.action_data = {
        "order_status": "processing",
        "payment_status": "paid",
        "refund_amount": "999.00",
        "currency": "INR",
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    db.commit()

    # The cancellation service must never
    # receive a refund action.
    def forbidden_cancellation_execution(*args, **kwargs):
        raise AssertionError(
            "CancellationExecutionService must not be called for refund initiation."
        )

    monkeypatch.setattr(
        conversations,
        "CancellationExecutionService",
        forbidden_cancellation_execution,
    )

    # Customer attempts to confirm the refund.
    response = client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={
            "message": "yes",
        },
    )

    # Refund execution is not implemented yet.
    assert response.status_code == 409

    assert response.json() == {
        "detail": "Refund execution is not available yet.",
    }

    db.expire_all()

    stored_order = db.get(
        Order,
        order_id,
    )

    stored_action = db.get(
        PendingAction,
        action_id,
    )

    # No cancellation occurred.
    assert stored_order.status == "processing"

    # The refund request remains pending.
    assert stored_action.status == "pending"
    assert stored_action.confirmed_at is None

    assert stored_action.action_data["action_performed"] is False

    # No refund record was created.
    refund = db.scalar(select(Refund).where(Refund.order_id == order_id))

    assert refund is None

    # No execution audit was created.
    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action_id
        )
    )

    assert audit is None

    # Confirmation handling should not invoke RAG.
    assert fake_pipeline.run_calls == 0


def test_eligible_refund_returns_pending_action(
    app,
    db,
    conversation,
):
    refund_pipeline = CountingFakePipeline(
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "reason_code": "ELIGIBLE",
            "reason": ("The order is eligible for a full refund."),
            "refund_amount": "1299.00",
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    app.dependency_overrides[get_pipeline] = lambda: refund_pipeline

    client = TestClient(app)

    response = client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={
            "message": "Refund ORD-10002",
        },
    )

    assert response.status_code == 201

    assert refund_pipeline.run_calls == 1

    data = response.json()

    pending = data["pending_action"]

    # The API must return a refund PendingAction.
    assert pending is not None

    assert pending["action_type"] == ("initiate_refund")

    assert pending["target_identifier"] == ("ORD-10002")

    assert pending["status"] == "pending"

    # Verify the PendingAction was actually stored.
    service = PendingActionService(db)

    stored_action = service.get_pending_action(conversation.id)

    assert stored_action is not None

    assert stored_action.id == pending["id"]

    assert stored_action.action_type == ("initiate_refund")

    assert stored_action.target_type == "order"

    assert stored_action.target_identifier == ("ORD-10002")

    assert stored_action.status == "pending"

    assert stored_action.confirmed_at is None

    # Verify the financial snapshot.
    action_data = stored_action.action_data

    assert action_data["refund_amount"] == ("1299.00")

    assert action_data["currency"] == "INR"

    assert action_data["eligible"] is True

    assert action_data["requires_confirmation"] is True

    assert action_data["action_performed"] is False


def test_no_rejects_pending_refund_without_pipeline(
    client,
    db,
    conversation,
    fake_pipeline,
):
    # Create a refund PendingAction.
    service = PendingActionService(db)

    action = service.create_pending_action(
        conversation_id=conversation.id,
        action_type="initiate_refund",
        target_type="order",
        target_identifier="ORD-10002",
        action_data={
            "order_status": "processing",
            "payment_status": "paid",
            "refund_amount": "1299.00",
            "currency": "INR",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    assert action.status == "pending"

    # Customer rejects the refund.
    response = client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={
            "message": "no",
        },
    )

    assert response.status_code == 201

    # Reload the PendingAction.
    db.refresh(action)

    # Verify rejection state.
    assert action.status == "rejected"

    assert action.confirmed_at is None

    assert action.action_data["action_performed"] is False

    # Rejection should not invoke the RAG pipeline.
    assert fake_pipeline.run_calls == 0

    data = response.json()

    # Verify refund-specific response.
    assert data["assistant_message"]["content"] == (
        "The pending refund request for "
        "ORD-10002 has been rejected. "
        "No refund has been initiated."
    )

    # No active PendingAction remains.
    assert data["pending_action"] is None

    assert service.get_pending_action(conversation.id) is None


def test_reject_pending_refund_via_exact_id(
    client,
    db,
    execution_case_factory,
    fake_pipeline,
):
    # Create a real test order, conversation,
    # and pending action.
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    order_id = order.id
    action_id = action.id

    # Convert the pending cancellation created
    # by the fixture into a refund request.
    action.action_type = "initiate_refund"

    action.action_data = {
        "order_status": "processing",
        "payment_status": "paid",
        "refund_amount": "999.00",
        "currency": "INR",
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    db.commit()

    # Reject the exact refund PendingAction.
    response = client.post(
        f"/api/v1/conversations/{conversation.id}/pending-actions/{action_id}/reject"
    )

    assert response.status_code == 200

    # Verify the API response.
    assert response.json() == {
        "id": action_id,
        "action_type": "initiate_refund",
        "target_identifier": order.order_number,
        "status": "rejected",
    }

    db.expire_all()

    stored_order = db.get(
        Order,
        order_id,
    )

    stored_action = db.get(
        PendingAction,
        action_id,
    )

    # The order must remain unchanged.
    assert stored_order is not None
    assert stored_order.status == "processing"

    # Only the pending action is rejected.
    assert stored_action is not None
    assert stored_action.status == "rejected"

    assert stored_action.confirmed_at is None

    assert stored_action.action_data["action_performed"] is False

    # No refund record should exist.
    refund = db.scalar(select(Refund).where(Refund.order_id == order_id))

    assert refund is None

    # No execution audit should exist.
    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action_id
        )
    )

    assert audit is None

    # Explicit rejection must not use the RAG pipeline.
    assert fake_pipeline.run_calls == 0

    # Verify the saved assistant response.
    messages_response = client.get(f"/api/v1/conversations/{conversation.id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]

    assert len(assistant_messages) == 1

    assert assistant_messages[0]["content"] == (
        f"The pending refund request for "
        f"{order.order_number} "
        f"has been rejected. "
        f"No refund has been initiated."
    )


def test_reject_pending_refund_endpoint_is_idempotent(
    client,
    db,
    execution_case_factory,
    fake_pipeline,
):
    # Create an order, conversation, and pending action.
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    order_id = order.id
    action_id = action.id
    conversation_id = conversation.id
    order_number = order.order_number

    # Convert the fixture's cancellation action
    # into a refund initiation action.
    action.action_type = "initiate_refund"

    action.action_data = {
        "order_status": "processing",
        "payment_status": "paid",
        "refund_amount": "999.00",
        "currency": "INR",
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    db.commit()

    url = f"/api/v1/conversations/{conversation_id}/pending-actions/{action_id}/reject"

    # Simulate clicking Reject twice.
    first_response = client.post(url)
    second_response = client.post(url)

    # Both requests should succeed.
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    expected_response = {
        "id": action_id,
        "action_type": "initiate_refund",
        "target_identifier": order_number,
        "status": "rejected",
    }

    assert first_response.json() == expected_response
    assert second_response.json() == expected_response

    # Reload database state.
    db.expire_all()

    stored_order = db.get(
        Order,
        order_id,
    )

    stored_action = db.get(
        PendingAction,
        action_id,
    )

    assert stored_order is not None
    assert stored_order.status == "processing"

    assert stored_action is not None
    assert stored_action.status == "rejected"
    assert stored_action.confirmed_at is None

    assert stored_action.action_data["action_performed"] is False

    # Rejecting must never initiate a refund.
    refund = db.scalar(select(Refund).where(Refund.order_id == order_id))

    assert refund is None

    # No execution audit should exist.
    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action_id
        )
    )

    assert audit is None

    # Rejecting must not invoke the RAG pipeline.
    assert fake_pipeline.run_calls == 0

    # Retrieve persisted conversation messages.
    messages_response = client.get(f"/api/v1/conversations/{conversation_id}/messages")

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assistant_messages = [
        message for message in messages if message["role"] == "assistant"
    ]

    # Idempotency: only one rejection message,
    # despite two API requests.
    assert len(assistant_messages) == 1

    assert assistant_messages[0]["content"] == (
        f"The pending refund request for "
        f"{order_number} "
        f"has been rejected. "
        f"No refund has been initiated."
    )


@pytest.mark.parametrize(
    "endpoint_suffix",
    [
        "execute",
        "confirm-and-execute",
    ],
)
def test_cancellation_execution_endpoints_reject_refund_actions(
    client,
    db,
    execution_case_factory,
    fake_pipeline,
    endpoint_suffix,
):
    # Create a real order, conversation,
    # and pending action in the test database.
    case = execution_case_factory(
        action_status="pending",
    )

    order = case["order"]
    conversation = case["conversation"]
    action = case["action"]

    order_id = order.id
    action_id = action.id
    conversation_id = conversation.id

    # Convert the action into a refund request.
    action.action_type = "initiate_refund"

    action.action_data = {
        "order_status": "processing",
        "payment_status": "paid",
        "refund_amount": "999.00",
        "currency": "INR",
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    db.commit()

    # Attempt to execute the refund through
    # a cancellation-specific endpoint.
    response = client.post(
        f"/api/v1/conversations/"
        f"{conversation_id}/pending-actions/"
        f"{action_id}/{endpoint_suffix}"
    )

    # Neither endpoint may execute refunds.
    assert response.status_code == 409

    assert response.json() == {
        "detail": ("Pending action cannot be executed by this endpoint."),
    }

    # Reload authoritative database state.
    db.expire_all()

    stored_order = db.get(
        Order,
        order_id,
    )

    stored_action = db.get(
        PendingAction,
        action_id,
    )

    # No order cancellation occurred.
    assert stored_order is not None
    assert stored_order.status == "processing"

    # The refund request must remain pending.
    assert stored_action is not None
    assert stored_action.action_type == "initiate_refund"
    assert stored_action.status == "pending"

    # Confirmation must not be recorded.
    assert stored_action.confirmed_at is None

    assert stored_action.action_data["action_performed"] is False

    # No refund was initiated.
    refund = db.scalar(select(Refund).where(Refund.order_id == order_id))

    assert refund is None

    # No execution audit was created.
    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action_id
        )
    )

    assert audit is None

    # Execution endpoints never invoke RAG.
    assert fake_pipeline.run_calls == 0

    # Rejected execution attempts should not
    # create customer-visible assistant messages.
    messages_response = client.get(f"/api/v1/conversations/{conversation_id}/messages")

    assert messages_response.status_code == 200

    assert messages_response.json() == []


@pytest.mark.parametrize(
    "scenario",
    [
        "ineligible",
        "tool_failed",
        "refund_status",
        "fallback",
    ],
)
def test_non_actionable_refund_results_do_not_create_pending_action(
    app,
    db,
    conversation,
    scenario,
):
    # A valid refund eligibility result.
    # We'll modify it for each negative scenario.
    eligible_data = {
        "found": True,
        "order_number": "ORD-10002",
        "status": "processing",
        "payment_status": "paid",
        "eligible": True,
        "reason": "The order is eligible for a full refund.",
        "refund_amount": "1299.00",
        "currency": "INR",
        "requires_confirmation": True,
        "action_performed": False,
    }

    # Configure the fake RAG pipeline
    # according to the scenario being tested.
    if scenario == "ineligible":
        pipeline_config = {
            "tool_used": True,
            "tool_name": "check_refund_eligibility",
            "tool_success": True,
            "tool_data": {
                **eligible_data,
                "eligible": False,
                "requires_confirmation": False,
            },
        }

    elif scenario == "tool_failed":
        pipeline_config = {
            "tool_used": True,
            "tool_name": "check_refund_eligibility",
            "tool_success": False,
            "tool_data": eligible_data,
        }

    elif scenario == "refund_status":
        pipeline_config = {
            "tool_used": True,
            "tool_name": "get_refund_status",
            "tool_success": True,
            "tool_data": {
                "order_number": "ORD-10002",
                "refund_number": "REF-10002",
                "status": "processing",
                "amount": "1299.00",
                "currency": "INR",
            },
        }

    elif scenario == "fallback":
        pipeline_config = {
            "tool_used": True,
            "tool_name": "check_refund_eligibility",
            "tool_success": True,
            "tool_data": eligible_data,
            "used_fallback": True,
        }

    refund_pipeline = CountingFakePipeline(
        **pipeline_config,
    )

    app.dependency_overrides[get_pipeline] = lambda: refund_pipeline

    client = TestClient(app)

    # Send the message through the actual API.
    response = client.post(
        f"/api/v1/conversations/{conversation.id}/messages",
        json={
            "message": "Check refund for ORD-10002",
        },
    )

    # The application must process the request.
    assert response.status_code == 201

    # The RAG pipeline must run exactly once.
    assert refund_pipeline.run_calls == 1

    data = response.json()

    # None of these scenarios should create
    # a new refund PendingAction.
    assert data["pending_action"] is None

    # Verify the database contains no active action.
    service = PendingActionService(db)

    stored_action = service.get_pending_action(conversation.id)

    assert stored_action is None

    # Verify the API also reports no active action.
    pending_response = client.get(
        f"/api/v1/conversations/{conversation.id}/pending-action"
    )

    assert pending_response.status_code == 200

    assert pending_response.json() is None
