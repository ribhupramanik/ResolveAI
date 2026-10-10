from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select, text

from src.db.database import SessionLocal, engine
from src.db.models import (
    ActionExecutionAudit,
    Conversation,
    Customer,
    Order,
    PendingAction,
    Refund,
)
from src.services.pending_action_service import (
    PendingActionService,
)


def test_pending_refund_cannot_execute_without_confirmation():

    # Never run this test against the development database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            # Create unique test records.
            token = uuid4().hex

            conversation = Conversation(
                title="Unconfirmed refund execution test",
            )

            customer = Customer(
                customer_code=f"TST-RFX-{token[:12]}",
                name="Refund Execution Test",
                email=f"refund-execution-{token}@example.com",
            )

            db.add_all(
                [
                    conversation,
                    customer,
                ]
            )

            db.flush()

            order = Order(
                order_number=(f"ORD-{uuid4().int % 10**18:018d}"),
                customer_id=customer.id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            # Create a refund PendingAction.
            service = PendingActionService(db)

            action = service.create_pending_action(
                conversation_id=conversation.id,
                action_type="initiate_refund",
                target_type="order",
                target_identifier=order.order_number,
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

            action_id = action.id
            order_id = order.id

            assert action.status == "pending"
            assert action.confirmed_at is None

            # Import here so the RED test can demonstrate
            # that the execution service is not implemented yet.
            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            # Attempt execution WITHOUT confirmation.
            result = RefundExecutionService(db).execute(action_id)

            # Execution must be rejected.
            assert result.success is False
            assert result.executed is False
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.action_status == "pending"

            assert result.reason == ("Refund has not been confirmed.")

            # Reload authoritative database state.
            db.flush()
            db.expire_all()

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            stored_order = db.get(
                Order,
                order_id,
            )

            # PendingAction remains unchanged.
            assert stored_action is not None
            assert stored_action.status == "pending"
            assert stored_action.confirmed_at is None

            assert stored_action.action_data["action_performed"] is False

            # The order remains unchanged.
            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            # No refund record was created.
            refund_count = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order_id)
            )

            assert refund_count == 0

            # No execution audit was created.
            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is None

        finally:
            # Never persist test records.
            db.rollback()


def test_confirmed_eligible_refund_creates_processing_refund():

    # Safety: always use the dedicated test database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            token = uuid4().hex

            conversation = Conversation(
                title="Confirmed refund execution test",
            )

            customer = Customer(
                customer_code=f"TST-RFX-{token[:12]}",
                name="Confirmed Refund Test",
                email=f"confirmed-refund-{token}@example.com",
            )

            db.add_all(
                [
                    conversation,
                    customer,
                ]
            )

            db.flush()

            order = Order(
                order_number=(f"ORD-{uuid4().int % 10**18:018d}"),
                customer_id=customer.id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            order_id = order.id
            order_number = order.order_number

            pending_service = PendingActionService(db)

            action = pending_service.create_pending_action(
                conversation_id=conversation.id,
                action_type="initiate_refund",
                target_type="order",
                target_identifier=order_number,
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

            action_id = action.id

            assert action.status == "pending"

            confirmed_action = pending_service.confirm_pending_action(conversation.id)

            assert confirmed_action is not None
            assert confirmed_action.id == action_id
            assert confirmed_action.status == "confirmed"
            assert confirmed_action.confirmed_at is not None

            # No Refund record should exist yet.
            existing_refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert existing_refunds == []

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            # A confirmed and eligible refund
            # should be successfully initiated.
            assert result.success is True
            assert result.executed is True
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.action_status == "executed"

            assert result.order_number == order_number
            assert result.order_status == "processing"

            db.flush()
            db.expire_all()

            stored_order = db.get(
                Order,
                order_id,
            )

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            # Order should remain unchanged.
            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            # PendingAction must be executed.
            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is True

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            # Exactly one refund should exist.
            assert len(refunds) == 1

            refund = refunds[0]

            assert refund.order_id == order_id
            assert refund.status == "processing"

            assert refund.amount == Decimal("1299.00")
            assert refund.currency == "INR"

            assert refund.refund_number
            assert refund.refund_number.startswith("REF-")

            assert refund.initiated_at is not None
            assert refund.completed_at is None
            assert refund.failure_reason is None

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is not None

            assert audit.outcome == "executed"
            assert audit.action_performed is True

            assert audit.action_type == "initiate_refund"
            assert audit.target_type == "order"

            assert audit.target_identifier == order_number

            # The audit must identify the
            # actual Refund created.
            assert audit.details is not None

            assert audit.details["refund_id"] == refund.id

            assert audit.details["refund_number"] == refund.refund_number

        finally:
            # Never persist test records.
            db.rollback()
