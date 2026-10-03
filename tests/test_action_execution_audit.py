from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.database import SessionLocal
from src.db.models import (
    ActionExecutionAudit,
    Conversation,
    Customer,
    Order,
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


def create_confirmed_cancellation(db):
    customer = Customer(
        customer_code="CUST-AUDIT-001",
        name="Audit Test",
        email="audit-test@example.com",
    )

    db.add(customer)
    db.flush()

    order = Order(
        order_number="ORD-AUDIT-001",
        customer_id=customer.id,
        status="processing",
        payment_status="paid",
        total_amount=Decimal("999.00"),
        currency="INR",
        shipping_address="Audit test address",
    )

    db.add(order)
    db.flush()

    conversation = Conversation(
        title="Audit test",
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
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    confirmed = service.confirm_pending_action(conversation.id)

    assert confirmed is not None

    return conversation, order, action


def test_execution_audit_can_be_created(
    db,
):
    conversation, order, action = create_confirmed_cancellation(db)

    audit = ActionExecutionAudit(
        pending_action_id=action.id,
        conversation_id=conversation.id,
        action_type=action.action_type,
        target_type=action.target_type,
        target_identifier=(action.target_identifier),
        outcome="executed",
        action_performed=True,
        previous_target_status="processing",
        final_target_status="cancelled",
        reason=("Order cancellation executed successfully."),
        details={
            "test": True,
        },
    )

    db.add(audit)
    db.flush()

    assert audit.id is not None

    assert audit.pending_action_id == action.id

    assert audit.target_identifier == order.order_number

    assert audit.outcome == "executed"

    assert audit.action_performed is True

    assert audit.previous_target_status == "processing"

    assert audit.final_target_status == "cancelled"

    assert audit.created_at is not None


def test_only_one_audit_allowed_per_pending_action(
    db,
):
    conversation, _, action = create_confirmed_cancellation(db)

    first = ActionExecutionAudit(
        pending_action_id=action.id,
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier=(action.target_identifier),
        outcome="executed",
        action_performed=True,
        previous_target_status="processing",
        final_target_status="cancelled",
        reason="First execution.",
    )

    db.add(first)
    db.flush()

    duplicate = ActionExecutionAudit(
        pending_action_id=action.id,
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier=(action.target_identifier),
        outcome="executed",
        action_performed=True,
        previous_target_status="processing",
        final_target_status="cancelled",
        reason="Duplicate execution.",
    )

    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.flush()

    db.rollback()
