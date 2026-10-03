from decimal import Decimal

import pytest
from sqlalchemy import select

from src.db.database import SessionLocal
from src.db.models import (
    ActionExecutionAudit,
    Conversation,
    Customer,
    Order,
)
from src.services.cancellation_execution_service import (
    CancellationExecutionService,
)
from src.services.pending_action_service import (
    PendingActionService,
)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def create_order(
    db,
    *,
    suffix: str,
    status: str = "processing",
):
    customer = Customer(
        customer_code=f"CUST-EXEC-{suffix}",
        name=f"Execution Test {suffix}",
        email=f"exec-{suffix}@example.com",
    )

    db.add(customer)
    db.flush()

    order = Order(
        order_number=f"ORD-9{suffix}",
        customer_id=customer.id,
        status=status,
        payment_status="paid",
        total_amount=Decimal("999.00"),
        currency="INR",
        shipping_address="Test address",
    )

    db.add(order)
    db.flush()

    return order


def create_confirmed_action(
    db,
    *,
    order_number: str,
    title: str,
):
    conversation = Conversation(
        title=title,
    )

    db.add(conversation)
    db.flush()

    service = PendingActionService(db)

    action = service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier=order_number,
        action_data={
            "order_status": "processing",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    confirmed = service.confirm_pending_action(conversation.id)

    assert confirmed is not None

    return action


def test_confirmed_processing_order_is_cancelled(
    db,
):
    order = create_order(
        db,
        suffix="001",
    )

    action = create_confirmed_action(
        db,
        order_number=order.order_number,
        title="Execute cancellation",
    )

    result = CancellationExecutionService(db).execute(action.id)

    db.refresh(order)
    db.refresh(action)

    assert result.success is True
    assert result.executed is True
    assert result.already_executed is False

    assert order.status == "cancelled"

    assert action.status == "executed"

    assert action.action_data["action_performed"] is True

    assert action.action_data["previous_order_status"] == "processing"

    assert action.action_data["final_order_status"] == "cancelled"

    assert action.action_data["executed_at"] is not None
    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert audit is not None

    assert audit.outcome == "executed"
    assert audit.action_performed is True

    assert audit.previous_target_status == "processing"

    assert audit.final_target_status == "cancelled"

    assert audit.target_identifier == order.order_number


def test_order_that_ships_after_confirmation_is_not_cancelled(
    db,
):
    order = create_order(
        db,
        suffix="002",
    )

    action = create_confirmed_action(
        db,
        order_number=order.order_number,
        title="Order shipped before execution",
    )

    # Simulate another system changing the order
    # after the customer confirmed cancellation.
    order.status = "shipped"
    db.flush()

    result = CancellationExecutionService(db).execute(action.id)

    db.refresh(order)
    db.refresh(action)

    assert result.success is False
    assert result.executed is False

    assert order.status == "shipped"

    assert action.status == "invalidated"

    assert action.action_data["action_performed"] is False

    assert action.action_data["current_order_status"] == "shipped"

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert audit is not None

    assert audit.outcome == "invalidated"
    assert audit.action_performed is False

    assert audit.previous_target_status == "shipped"

    assert audit.final_target_status == "shipped"


def test_pending_action_cannot_execute(
    db,
):
    order = create_order(
        db,
        suffix="003",
    )

    conversation = Conversation(
        title="Unconfirmed cancellation",
    )

    db.add(conversation)
    db.flush()

    action = PendingActionService(db).create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier=order.order_number,
        action_data={
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    result = CancellationExecutionService(db).execute(action.id)

    db.refresh(order)
    db.refresh(action)

    assert result.success is False
    assert result.executed is False

    assert order.status == "processing"
    assert action.status == "pending"

    audit = db.scalar(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    )

    assert audit is None


def test_cancellation_execution_is_idempotent(
    db,
):
    order = create_order(
        db,
        suffix="004",
    )

    action = create_confirmed_action(
        db,
        order_number=order.order_number,
        title="Idempotent cancellation",
    )

    service = CancellationExecutionService(db)

    first = service.execute(action.id)
    second = service.execute(action.id)

    db.refresh(order)
    db.refresh(action)

    assert first.success is True
    assert first.executed is True
    assert first.already_executed is False

    assert second.success is True
    assert second.executed is False
    assert second.already_executed is True

    assert order.status == "cancelled"
    assert action.status == "executed"

    audits = db.scalars(
        select(ActionExecutionAudit).where(
            ActionExecutionAudit.pending_action_id == action.id
        )
    ).all()

    assert len(audits) == 1

    assert audits[0].outcome == "executed"
    assert audits[0].action_performed is True


def test_missing_pending_action_does_not_execute(
    db,
):
    result = CancellationExecutionService(db).execute(99999999)

    assert result.success is False
    assert result.executed is False
    assert result.already_executed is False

    assert result.action_id is None
