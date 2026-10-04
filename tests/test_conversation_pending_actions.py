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
)
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
