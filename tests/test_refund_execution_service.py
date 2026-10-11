from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
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


def test_confirmed_refund_is_invalidated_when_order_ships_before_execution():

    # Safety: use only the test database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            # ----------------------------------
            # 1. Create an eligible order
            # ----------------------------------

            token = uuid4().hex

            conversation = Conversation(
                title="Refund invalidation test",
            )

            customer = Customer(
                customer_code=f"TST-RFI-{token[:12]}",
                name="Refund Invalidation Test",
                email=f"refund-invalidation-{token}@example.com",
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

            # ----------------------------------
            # 2. Create the refund PendingAction
            # ----------------------------------

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

            # ----------------------------------
            # 3. Confirm the refund
            # ----------------------------------

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # ----------------------------------
            # 4. Simulate the order being shipped
            # ----------------------------------

            # The order was processing when eligibility
            # was originally checked.
            #
            # It has now shipped BEFORE refund execution.

            order.status = "shipped"

            db.flush()

            # ----------------------------------
            # 5. Attempt refund execution
            # ----------------------------------

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            # The refund must not execute.
            assert result.success is False
            assert result.executed is False
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.order_number == order_number
            assert result.order_status == "shipped"

            # IMPORTANT:
            # The confirmed action must now be invalidated.
            assert result.action_status == "invalidated"

            assert "shipped" in result.reason.lower()

            # ----------------------------------
            # 6. Reload database state
            # ----------------------------------

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

            # The order remains shipped.
            assert stored_order is not None
            assert stored_order.status == "shipped"
            assert stored_order.payment_status == "paid"

            # The PendingAction records invalidation.
            assert stored_action is not None
            assert stored_action.status == "invalidated"

            # Confirmation genuinely happened earlier.
            assert stored_action.confirmed_at is not None

            # But no refund was performed.
            assert stored_action.action_data["action_performed"] is False

            # The invalidation reason should be stored.
            assert (
                "shipped"
                in stored_action.action_data["execution_blocked_reason"].lower()
            )

            # ----------------------------------
            # 7. Verify no Refund was created
            # ----------------------------------

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert refunds == []

            # ----------------------------------
            # 8. Verify execution audit
            # ----------------------------------

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is not None

            assert audit.outcome == "invalidated"
            assert audit.action_performed is False

            assert audit.action_type == "initiate_refund"
            assert audit.target_type == "order"

            assert audit.target_identifier == order_number

            assert audit.previous_target_status == "shipped"
            assert audit.final_target_status == "shipped"

            assert "shipped" in audit.reason.lower()

        finally:
            # Roll back all test data.
            db.rollback()


def test_confirmed_refund_is_invalidated_when_payment_status_changes():

    # Never use the development database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            # ----------------------------------
            # 1. Create an initially eligible order
            # ----------------------------------

            token = uuid4().hex

            conversation = Conversation(
                title="Refund payment revalidation test",
            )

            customer = Customer(
                customer_code=f"TST-RFP-{token[:12]}",
                name="Refund Payment Test",
                email=f"refund-payment-{token}@example.com",
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

            # ----------------------------------
            # 2. Create a refund PendingAction
            # ----------------------------------

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

            # ----------------------------------
            # 3. Confirm the refund
            # ----------------------------------

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # ----------------------------------
            # 4. Change the payment status
            # ----------------------------------

            # The order was paid when refund
            # eligibility was originally checked.
            #
            # Its payment status changes before
            # the refund is executed.

            order.payment_status = "pending"

            db.flush()

            # ----------------------------------
            # 5. Attempt refund execution
            # ----------------------------------

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            # Execution must fail.
            assert result.success is False
            assert result.executed is False
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.action_status == "invalidated"

            assert result.order_number == order_number
            assert result.order_status == "processing"

            assert "not been paid" in result.reason.lower()

            # ----------------------------------
            # 6. Reload authoritative database state
            # ----------------------------------

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

            # Verify the order was not modified
            # by the refund execution service.
            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "pending"

            # Verify PendingAction invalidation.
            assert stored_action is not None
            assert stored_action.status == "invalidated"

            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is False

            assert (
                "not been paid"
                in stored_action.action_data["execution_blocked_reason"].lower()
            )

            # ----------------------------------
            # 7. Verify no Refund was created
            # ----------------------------------

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert refunds == []

            # ----------------------------------
            # 8. Verify execution audit
            # ----------------------------------

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is not None

            assert audit.outcome == "invalidated"
            assert audit.action_performed is False

            assert audit.action_type == "initiate_refund"
            assert audit.target_type == "order"

            assert audit.target_identifier == order_number

            assert audit.previous_target_status == "processing"
            assert audit.final_target_status == "processing"

            assert "not been paid" in audit.reason.lower()

            assert audit.details is not None
            assert audit.details["blocked_stage"] == "execution_revalidation"

        finally:
            # Roll back all test data.
            db.rollback()


@pytest.mark.parametrize(
    "existing_refund_status, expected_reason",
    [
        (
            "processing",
            "A refund is already being processed for this order.",
        ),
        (
            "completed",
            "This order has already been refunded.",
        ),
    ],
)
def test_confirmed_refund_is_invalidated_when_refund_already_exists(
    existing_refund_status,
    expected_reason,
):
    # ------------------------------------------
    # 1. Verify the test database
    # ------------------------------------------

    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            # ------------------------------------------
            # 2. Create an initially eligible order
            # ------------------------------------------

            token = uuid4().hex

            conversation = Conversation(
                title="Duplicate refund prevention test",
            )

            customer = Customer(
                customer_code=f"TST-RFD-{token[:12]}",
                name="Duplicate Refund Test",
                email=f"duplicate-refund-{token}@example.com",
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

            # ------------------------------------------
            # 3. Create the refund PendingAction
            # ------------------------------------------

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

            # ------------------------------------------
            # 4. Confirm the refund request
            # ------------------------------------------

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # ------------------------------------------
            # 5. Simulate another refund being initiated
            # ------------------------------------------

            # The existing refund is created AFTER
            # the PendingAction was confirmed but
            # BEFORE our execution attempt.

            now = datetime.now(UTC)

            existing_refund = Refund(
                refund_number=f"REF-{uuid4().hex.upper()}",
                order_id=order_id,
                status=existing_refund_status,
                amount=Decimal("1299.00"),
                currency="INR",
                initiated_at=now,
                completed_at=(now if existing_refund_status == "completed" else None),
                failure_reason=None,
            )

            db.add(existing_refund)
            db.flush()

            existing_refund_id = existing_refund.id

            # Verify exactly one refund exists
            # before the execution attempt.

            existing_count = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order_id)
            )

            assert existing_count == 1

            # ------------------------------------------
            # 6. Attempt execution
            # ------------------------------------------

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            # A new refund must not be initiated.
            assert result.success is False
            assert result.executed is False
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.action_status == "invalidated"

            assert result.order_number == order_number
            assert result.order_status == "processing"

            assert result.reason == expected_reason

            # ------------------------------------------
            # 7. Reload authoritative database state
            # ------------------------------------------

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

            # The order must remain unchanged.
            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            # The PendingAction must be invalidated.
            assert stored_action is not None
            assert stored_action.status == "invalidated"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is False

            assert (
                stored_action.action_data["execution_blocked_reason"] == expected_reason
            )

            # ------------------------------------------
            # 8. Verify no duplicate Refund was created
            # ------------------------------------------

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            # Only the original refund should exist.
            assert len(refunds) == 1

            assert refunds[0].id == existing_refund_id
            assert refunds[0].status == existing_refund_status

            assert refunds[0].amount == Decimal("1299.00")
            assert refunds[0].currency == "INR"

            # ------------------------------------------
            # 9. Verify invalidation audit
            # ------------------------------------------

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is not None

            assert audit.outcome == "invalidated"
            assert audit.action_performed is False

            assert audit.action_type == "initiate_refund"
            assert audit.target_type == "order"

            assert audit.target_identifier == order_number

            assert audit.previous_target_status == "processing"
            assert audit.final_target_status == "processing"

            assert audit.reason == expected_reason

            assert audit.details is not None

            assert audit.details["blocked_stage"] == "execution_revalidation"

        finally:
            # Roll back all test data.
            db.rollback()
