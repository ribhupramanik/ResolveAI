from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from queue import Queue
from threading import Barrier
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text

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


def test_confirmed_refund_can_retry_after_previous_failed_refund():
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            token = uuid4().hex

            # Create the conversation and customer.
            conversation = Conversation(
                title="Failed refund retry test",
            )

            customer = Customer(
                customer_code=f"TST-RFR-{token[:12]}",
                name="Failed Refund Retry Test",
                email=f"failed-refund-retry-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            # Create an eligible order.
            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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

            # Create a PREVIOUSLY FAILED refund.
            failure_reason = "Previous refund initiation failed."

            failed_refund = Refund(
                refund_number=f"REF-{uuid4().hex.upper()}",
                order_id=order_id,
                status="failed",
                amount=Decimal("1299.00"),
                currency="INR",
                initiated_at=datetime.now(UTC),
                completed_at=None,
                failure_reason=failure_reason,
            )

            db.add(failed_refund)
            db.flush()

            failed_refund_id = failed_refund.id
            failed_refund_number = failed_refund.refund_number

            # Create a new refund PendingAction.
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

            # Confirm the new refund request.
            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # Execute the new refund request.
            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            assert result.success is True
            assert result.executed is True
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.action_status == "executed"
            assert result.order_number == order_number

            # Reload database state.
            db.flush()
            db.expire_all()

            stored_action = db.get(PendingAction, action_id)
            stored_order = db.get(Order, order_id)

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.confirmed_at is not None
            assert stored_action.action_data["action_performed"] is True

            # Both refund attempts must exist.
            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 2

            # The original failed refund must be preserved.
            stored_failed_refund = next(
                refund for refund in refunds if refund.id == failed_refund_id
            )

            assert stored_failed_refund.status == "failed"
            assert stored_failed_refund.refund_number == failed_refund_number
            assert stored_failed_refund.failure_reason == failure_reason

            # Identify the newly initiated refund.
            new_refunds = [
                refund for refund in refunds if refund.id != failed_refund_id
            ]

            assert len(new_refunds) == 1

            new_refund = new_refunds[0]

            assert new_refund.status == "processing"
            assert new_refund.amount == Decimal("1299.00")
            assert new_refund.currency == "INR"

            assert new_refund.refund_number.startswith("REF-")
            assert new_refund.refund_number != failed_refund_number

            assert new_refund.initiated_at is not None
            assert new_refund.completed_at is None
            assert new_refund.failure_reason is None

            # Verify the execution audit references
            # the NEW refund, not the failed one.
            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is not None
            assert audit.outcome == "executed"
            assert audit.action_performed is True
            assert audit.action_type == "initiate_refund"

            assert audit.details is not None
            assert audit.details["refund_id"] == new_refund.id
            assert audit.details["refund_number"] == new_refund.refund_number

            # The PendingAction must also identify
            # the newly created refund.
            assert stored_action.action_data["refund_id"] == new_refund.id

            assert (
                stored_action.action_data["refund_number"] == new_refund.refund_number
            )

        finally:
            db.rollback()


def test_confirmed_refund_is_invalidated_when_order_amount_changes():

    # Safety: never use the development database.
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
                title="Refund amount revalidation test",
            )

            customer = Customer(
                customer_code=f"TST-RFA-{token[:12]}",
                name="Refund Amount Test",
                email=f"refund-amount-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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
            # 2. Create refund PendingAction
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
            # 3. Explicitly confirm the refund
            # ----------------------------------

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # ----------------------------------
            # 4. Change the order amount
            # ----------------------------------

            # Original confirmed amount: 1299.00
            # Current authoritative amount: 1499.00

            order.total_amount = Decimal("1499.00")

            db.flush()

            # ----------------------------------
            # 5. Attempt refund execution
            # ----------------------------------

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            # The stale confirmation must not execute.
            assert result.success is False
            assert result.executed is False
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.order_number == order_number
            assert result.order_status == "processing"

            # New requirement:
            # The confirmed action must be invalidated.
            assert result.action_status == "invalidated"

            expected_reason = "Refund amount no longer matches the order."

            assert result.reason == expected_reason

            # ----------------------------------
            # 6. Verify persisted database state
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

            # The execution service must not
            # modify the authoritative order.
            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("1499.00")

            # PendingAction must be invalidated.
            assert stored_action is not None
            assert stored_action.status == "invalidated"

            # Preserve evidence of customer confirmation.
            assert stored_action.confirmed_at is not None

            # No refund was performed.
            assert stored_action.action_data["action_performed"] is False

            # Preserve the original financial snapshot.
            assert stored_action.action_data["refund_amount"] == "1299.00"

            assert stored_action.action_data["currency"] == "INR"

            assert (
                stored_action.action_data["execution_blocked_reason"] == expected_reason
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

            assert audit.reason == expected_reason

            assert audit.details is not None

            assert audit.details["blocked_stage"] == "execution_revalidation"

        finally:
            # Never persist test records.
            db.rollback()


def test_confirmed_refund_is_invalidated_when_order_currency_changes():

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
                title="Refund currency revalidation test",
            )

            customer = Customer(
                customer_code=f"TST-RFC-{token[:12]}",
                name="Refund Currency Test",
                email=f"refund-currency-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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
            # 4. Explicitly confirm the refund
            # ------------------------------------------

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # ------------------------------------------
            # 5. Change the authoritative currency
            # ------------------------------------------

            # Original confirmed currency: INR
            # Current order currency: USD
            #
            # The numeric amount remains unchanged.

            order.currency = "USD"

            db.flush()

            # ------------------------------------------
            # 6. Attempt refund execution
            # ------------------------------------------

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            result = RefundExecutionService(db).execute(action_id)

            assert result.success is False
            assert result.executed is False
            assert result.already_executed is False

            assert result.action_id == action_id
            assert result.order_number == order_number
            assert result.order_status == "processing"

            # New requirement:
            # The stale confirmation must be invalidated.
            assert result.action_status == "invalidated"

            expected_reason = "Refund currency no longer matches the order."

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

            # The execution service must not change
            # the authoritative order.
            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            assert stored_order.total_amount == Decimal("1299.00")

            assert stored_order.currency == "USD"

            # ------------------------------------------
            # 8. Verify PendingAction invalidation
            # ------------------------------------------

            assert stored_action is not None

            assert stored_action.status == "invalidated"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is False

            # The original confirmed financial
            # snapshot must remain unchanged.
            assert stored_action.action_data["refund_amount"] == "1299.00"

            assert stored_action.action_data["currency"] == "INR"

            assert (
                stored_action.action_data["execution_blocked_reason"] == expected_reason
            )

            # ------------------------------------------
            # 9. Verify no Refund was created
            # ------------------------------------------

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert refunds == []

            # ------------------------------------------
            # 10. Verify execution audit
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
            # Never persist test records.
            db.rollback()


def test_refund_execution_changes_roll_back_atomically():

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
            # 2. Create an eligible order
            # ------------------------------------------

            token = uuid4().hex

            conversation = Conversation(
                title="Refund transaction rollback test",
            )

            customer = Customer(
                customer_code=f"TST-RFT-{token[:12]}",
                name="Refund Transaction Test",
                email=f"refund-transaction-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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
            # 3. Create and confirm the PendingAction
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

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # Flush the confirmed state BEFORE
            # starting the savepoint.
            db.flush()

            # ------------------------------------------
            # 4. Create a PostgreSQL SAVEPOINT
            # ------------------------------------------

            # The confirmed PendingAction is now part
            # of the outer transaction.
            #
            # Only changes made AFTER this savepoint
            # should be rolled back.

            savepoint = db.begin_nested()

            try:
                # --------------------------------------
                # 5. Execute the refund
                # --------------------------------------

                from src.services.refund_execution_service import (
                    RefundExecutionService,
                )

                result = RefundExecutionService(db).execute(action_id)

                assert result.success is True
                assert result.executed is True
                assert result.already_executed is False
                assert result.action_status == "executed"

                db.flush()

                # --------------------------------------
                # 6. Verify execution changes exist
                # --------------------------------------

                executed_action = db.get(
                    PendingAction,
                    action_id,
                )

                assert executed_action is not None
                assert executed_action.status == "executed"

                assert executed_action.action_data["action_performed"] is True

                refund_count = db.scalar(
                    select(func.count(Refund.id)).where(Refund.order_id == order_id)
                )

                assert refund_count == 1

                audit = db.scalar(
                    select(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                )

                assert audit is not None
                assert audit.outcome == "executed"
                assert audit.action_performed is True

            finally:
                # --------------------------------------
                # 7. Roll back the SAVEPOINT
                # --------------------------------------

                # This must undo:
                # - Refund INSERT
                # - PendingAction UPDATE
                # - ActionExecutionAudit INSERT

                savepoint.rollback()

            # ------------------------------------------
            # 8. Reload database state after rollback
            # ------------------------------------------

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

            assert stored_order.total_amount == Decimal("1299.00")

            assert stored_order.currency == "INR"

            # ------------------------------------------
            # 9. Verify PendingAction was restored
            # ------------------------------------------

            assert stored_action is not None

            # The confirmation happened before
            # the savepoint and must remain intact.
            assert stored_action.status == "confirmed"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is False

            assert stored_action.action_data["refund_amount"] == "1299.00"

            # There must be no execution metadata.
            assert "refund_id" not in stored_action.action_data

            assert "refund_number" not in stored_action.action_data

            # ------------------------------------------
            # 10. Verify Refund was rolled back
            # ------------------------------------------

            refund_count = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order_id)
            )

            assert refund_count == 0

            # ------------------------------------------
            # 11. Verify audit was rolled back
            # ------------------------------------------

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is None

        finally:
            # Roll back the outer transaction
            # to remove all test data.
            db.rollback()


def test_refund_execution_is_idempotent_when_called_twice():

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
            # 2. Create an eligible order
            # ------------------------------------------

            token = uuid4().hex

            conversation = Conversation(
                title="Refund execution idempotency test",
            )

            customer = Customer(
                customer_code=f"TST-RFI-{token[:12]}",
                name="Refund Idempotency Test",
                email=f"refund-idempotency-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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
            # 3. Create and confirm PendingAction
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

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            # ------------------------------------------
            # 4. FIRST execution
            # ------------------------------------------

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            execution_service = RefundExecutionService(db)

            first_result = execution_service.execute(action_id)

            assert first_result.success is True
            assert first_result.executed is True
            assert first_result.already_executed is False

            assert first_result.action_status == "executed"

            db.flush()

            # ------------------------------------------
            # 5. Record the first execution details
            # ------------------------------------------

            refunds_before = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds_before) == 1

            original_refund = refunds_before[0]

            original_refund_id = original_refund.id
            original_refund_number = original_refund.refund_number
            original_initiated_at = original_refund.initiated_at

            original_audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert original_audit is not None

            original_audit_id = original_audit.id

            original_action = db.get(
                PendingAction,
                action_id,
            )

            assert original_action is not None
            assert original_action.status == "executed"

            original_action_data = dict(original_action.action_data)

            # ------------------------------------------
            # 6. SECOND execution
            # ------------------------------------------

            # Simulate the same refund execution
            # being requested again.
            #
            # This must NOT initiate another refund.

            second_result = execution_service.execute(action_id)

            # ------------------------------------------
            # 7. Verify idempotent response
            # ------------------------------------------

            assert second_result.success is True

            # No NEW execution occurred.
            assert second_result.executed is False

            # The service recognized the
            # previously executed PendingAction.
            assert second_result.already_executed is True

            assert second_result.action_id == action_id
            assert second_result.action_status == "executed"

            assert second_result.order_number == order_number

            # ------------------------------------------
            # 8. Reload authoritative database state
            # ------------------------------------------

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

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is True

            # The second execution must not
            # overwrite the original metadata.
            assert stored_action.action_data == original_action_data

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            # ------------------------------------------
            # 9. Verify exactly ONE Refund exists
            # ------------------------------------------

            refunds_after = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds_after) == 1

            stored_refund = refunds_after[0]

            assert stored_refund.id == original_refund_id

            assert stored_refund.refund_number == original_refund_number

            assert stored_refund.initiated_at == original_initiated_at

            assert stored_refund.status == "processing"
            assert stored_refund.amount == Decimal("1299.00")
            assert stored_refund.currency == "INR"

            # ------------------------------------------
            # 10. Verify exactly ONE audit exists
            # ------------------------------------------

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            audit = audits[0]

            assert audit.id == original_audit_id

            assert audit.outcome == "executed"
            assert audit.action_performed is True

            assert audit.details["refund_id"] == original_refund_id

            assert audit.details["refund_number"] == original_refund_number

        finally:
            # Never persist test data.
            db.rollback()


def test_refund_execution_is_idempotent_after_commit_in_new_session():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    conversation_id = None
    customer_id = None
    order_id = None
    action_id = None

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            conversation = Conversation(
                title="Cross-session refund idempotency test",
            )

            customer = Customer(
                customer_code=f"TST-RCS-{token[:12]}",
                name="Cross-Session Refund Test",
                email=f"refund-cross-session-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            conversation_id = conversation.id
            customer_id = customer.id

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
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
                conversation_id=conversation_id,
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

            confirmed = pending_service.confirm_pending_action(conversation_id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            first_result = RefundExecutionService(db).execute(action_id)

            assert first_result.success is True
            assert first_result.executed is True
            assert first_result.already_executed is False
            assert first_result.action_status == "executed"

            db.commit()

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            second_result = RefundExecutionService(db).execute(action_id)

            assert second_result.success is True
            assert second_result.executed is False
            assert second_result.already_executed is True

            assert second_result.action_id == action_id
            assert second_result.action_status == "executed"
            assert second_result.order_number == order_number

            stored_action = db.get(PendingAction, action_id)

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.action_data["action_performed"] is True

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            refund = refunds[0]

            assert refund.status == "processing"
            assert refund.amount == Decimal("1299.00")
            assert refund.currency == "INR"

            assert stored_action.action_data["refund_id"] == refund.id

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            audit = audits[0]

            assert audit.outcome == "executed"
            assert audit.action_performed is True
            assert audit.details["refund_id"] == refund.id
            assert audit.details["refund_number"] == refund.refund_number

            db.rollback()

    finally:
        if action_id is not None:
            with SessionLocal() as db:
                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


def test_executed_refund_fails_safely_when_refund_record_is_missing():
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            token = uuid4().hex

            conversation = Conversation(
                title="Missing executed refund test",
            )

            customer = Customer(
                customer_code=f"TST-RFM-{token[:12]}",
                name="Missing Refund Test",
                email=f"missing-refund-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            execution_service = RefundExecutionService(db)

            first_result = execution_service.execute(action_id)

            assert first_result.success is True
            assert first_result.executed is True
            assert first_result.already_executed is False

            db.flush()

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            original_refund = refunds[0]
            original_refund_id = original_refund.id

            stored_action = db.get(PendingAction, action_id)

            assert stored_action is not None
            assert stored_action.status == "executed"

            original_action_data = dict(stored_action.action_data)

            original_audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert original_audit is not None

            original_audit_id = original_audit.id

            db.delete(original_refund)
            db.flush()
            db.expire_all()

            assert db.get(Refund, original_refund_id) is None

            second_result = execution_service.execute(action_id)

            assert second_result.success is False
            assert second_result.executed is False
            assert second_result.already_executed is False

            assert second_result.action_id == action_id
            assert second_result.action_status == "executed"

            assert second_result.order_number == order_number
            assert second_result.order_status == "processing"

            assert second_result.reason == (
                "Previously executed refund action has inconsistent records."
            )

            db.flush()
            db.expire_all()

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            assert stored_action is not None
            assert stored_action.status == "executed"

            assert stored_action.action_data == original_action_data

            assert stored_action.action_data["refund_id"] == original_refund_id

            refund_count = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order_id)
            )

            assert refund_count == 0

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            assert audits[0].id == original_audit_id
            assert audits[0].outcome == "executed"

        finally:
            db.rollback()


def test_executed_refund_fails_safely_when_audit_refund_id_is_inconsistent():
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            token = uuid4().hex

            conversation = Conversation(
                title="Inconsistent refund audit test",
            )

            customer = Customer(
                customer_code=f"TST-RIA-{token[:12]}",
                name="Refund Audit Integrity Test",
                email=f"refund-audit-integrity-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
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

            confirmed = pending_service.confirm_pending_action(conversation.id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            from src.services.refund_execution_service import (
                RefundExecutionService,
            )

            execution_service = RefundExecutionService(db)

            first_result = execution_service.execute(action_id)

            assert first_result.success is True
            assert first_result.executed is True
            assert first_result.already_executed is False

            db.flush()

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            original_refund = refunds[0]
            original_refund_id = original_refund.id
            original_refund_number = original_refund.refund_number

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            assert stored_action is not None
            assert stored_action.status == "executed"

            original_action_data = dict(stored_action.action_data)

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is not None
            assert audit.outcome == "executed"
            assert audit.action_performed is True
            assert audit.details["refund_id"] == original_refund_id

            original_audit_id = audit.id

            incorrect_refund_id = original_refund_id + 1

            audit.details = {
                **audit.details,
                "refund_id": incorrect_refund_id,
            }

            db.flush()
            db.expire_all()

            second_result = execution_service.execute(action_id)

            assert second_result.success is False
            assert second_result.executed is False
            assert second_result.already_executed is False

            assert second_result.action_id == action_id
            assert second_result.action_status == "executed"
            assert second_result.order_number == order_number
            assert second_result.order_status == "processing"

            assert second_result.reason == (
                "Previously executed refund action has inconsistent records."
            )

            db.flush()
            db.expire_all()

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.action_data == original_action_data

            refunds_after = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds_after) == 1

            stored_refund = refunds_after[0]

            assert stored_refund.id == original_refund_id
            assert stored_refund.refund_number == original_refund_number
            assert stored_refund.status == "processing"
            assert stored_refund.amount == Decimal("1299.00")
            assert stored_refund.currency == "INR"

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            stored_audit = audits[0]

            assert stored_audit.id == original_audit_id
            assert stored_audit.outcome == "executed"
            assert stored_audit.action_performed is True

            assert stored_audit.details["refund_id"] == incorrect_refund_id

            assert stored_audit.details["refund_number"] == original_refund_number

        finally:
            db.rollback()


def test_concurrent_refund_actions_for_same_order_create_one_refund():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    conversation_ids = []
    action_ids = []

    customer_id = None
    order_id = None
    order_number = None

    setup_committed = False

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            customer = Customer(
                customer_code=f"TST-RCC-{token[:12]}",
                name="Concurrent Refund Test",
                email=f"concurrent-refund-{token}@example.com",
            )

            conversation_a = Conversation(
                title="Concurrent refund conversation A",
            )

            conversation_b = Conversation(
                title="Concurrent refund conversation B",
            )

            db.add_all(
                [
                    customer,
                    conversation_a,
                    conversation_b,
                ]
            )

            db.flush()

            customer_id = customer.id

            conversation_ids = [
                conversation_a.id,
                conversation_b.id,
            ]

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
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

            for conversation_id in conversation_ids:
                action = pending_service.create_pending_action(
                    conversation_id=conversation_id,
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

                action_ids.append(action.id)

                confirmed = pending_service.confirm_pending_action(conversation_id)

                assert confirmed is not None
                assert confirmed.id == action.id
                assert confirmed.status == "confirmed"
                assert confirmed.confirmed_at is not None

            assert len(action_ids) == 2
            assert action_ids[0] != action_ids[1]

            db.commit()
            setup_committed = True

        barrier = Barrier(2)

        def execute_refund_in_separate_session(action_id):
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                from src.services.refund_execution_service import (
                    RefundExecutionService,
                )

                barrier.wait(timeout=20)

                result = RefundExecutionService(db).execute(action_id)

                db.commit()

                return result

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    execute_refund_in_separate_session,
                    action_id,
                )
                for action_id in action_ids
            ]

            results = [future.result(timeout=60) for future in futures]

        assert len(results) == 2

        successful_results = [result for result in results if result.success is True]

        invalidated_results = [
            result for result in results if result.action_status == "invalidated"
        ]

        assert len(successful_results) == 1
        assert len(invalidated_results) == 1

        successful_result = successful_results[0]
        invalidated_result = invalidated_results[0]

        assert successful_result.executed is True
        assert successful_result.already_executed is False
        assert successful_result.action_status == "executed"

        assert invalidated_result.success is False
        assert invalidated_result.executed is False
        assert invalidated_result.already_executed is False

        assert (
            invalidated_result.reason
            == "A refund is already being processed for this order."
        )

        assert successful_result.action_id != invalidated_result.action_id

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            stored_order = db.get(Order, order_id)

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("1299.00")
            assert stored_order.currency == "INR"

            actions = db.scalars(
                select(PendingAction).where(PendingAction.id.in_(action_ids))
            ).all()

            assert len(actions) == 2

            action_by_id = {action.id: action for action in actions}

            executed_action = action_by_id[successful_result.action_id]

            invalidated_action = action_by_id[invalidated_result.action_id]

            assert executed_action.status == "executed"
            assert executed_action.confirmed_at is not None

            assert executed_action.action_data["action_performed"] is True

            assert invalidated_action.status == "invalidated"
            assert invalidated_action.confirmed_at is not None

            assert invalidated_action.action_data["action_performed"] is False

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            refund = refunds[0]

            assert refund.status == "processing"
            assert refund.amount == Decimal("1299.00")
            assert refund.currency == "INR"

            assert executed_action.action_data["refund_id"] == refund.id

            assert executed_action.action_data["refund_number"] == refund.refund_number

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id.in_(action_ids)
                )
            ).all()

            assert len(audits) == 2

            audit_by_action_id = {audit.pending_action_id: audit for audit in audits}

            executed_audit = audit_by_action_id[successful_result.action_id]

            invalidated_audit = audit_by_action_id[invalidated_result.action_id]

            assert executed_audit.outcome == "executed"
            assert executed_audit.action_performed is True

            assert executed_audit.details["refund_id"] == refund.id

            assert executed_audit.details["refund_number"] == refund.refund_number

            assert invalidated_audit.outcome == "invalidated"
            assert invalidated_audit.action_performed is False

            assert (
                invalidated_audit.reason
                == "A refund is already being processed for this order."
            )

            db.rollback()

    finally:
        if setup_committed:
            with SessionLocal() as db:
                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id.in_(action_ids)
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(
                    delete(PendingAction).where(PendingAction.id.in_(action_ids))
                )

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id.in_(conversation_ids))
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


def test_refund_execution_waits_for_postgres_order_lock():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    conversation_id = None
    customer_id = None
    order_id = None
    action_id = None

    setup_committed = False
    lock_db = None

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            conversation = Conversation(title="PostgreSQL refund lock contention test")

            customer = Customer(
                customer_code=f"TST-RLC-{token[:12]}",
                name="Refund Lock Contention Test",
                email=f"refund-lock-{token}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            conversation_id = conversation.id
            customer_id = customer.id

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
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
                conversation_id=conversation_id,
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

            confirmed = pending_service.confirm_pending_action(conversation_id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            db.commit()
            setup_committed = True

        lock_db = SessionLocal()

        assert (
            lock_db.execute(text("SELECT current_database()")).scalar_one()
            == "resolveai_test"
        )

        locker_pid = lock_db.scalar(text("SELECT pg_backend_pid()"))

        locked_order = lock_db.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )

        assert locked_order is not None
        assert locked_order.order_number == order_number

        worker_pid_queue = Queue()

        def execute_refund_in_worker():
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                db.execute(text("SET LOCAL lock_timeout = '20000ms'"))

                worker_pid = db.scalar(text("SELECT pg_backend_pid()"))

                worker_pid_queue.put(worker_pid)

                from src.services.refund_execution_service import (
                    RefundExecutionService,
                )

                result = RefundExecutionService(db).execute(action_id)

                db.commit()

                return result

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute_refund_in_worker)

            try:
                worker_pid = worker_pid_queue.get(timeout=10)

                assert worker_pid != locker_pid

                blocked = False
                deadline = monotonic() + 10

                with SessionLocal() as observer:
                    assert (
                        observer.execute(text("SELECT current_database()")).scalar_one()
                        == "resolveai_test"
                    )

                    while monotonic() < deadline:
                        blocking_pids = observer.scalar(
                            text("SELECT pg_blocking_pids(:worker_pid)"),
                            {"worker_pid": worker_pid},
                        )

                        if locker_pid in blocking_pids:
                            blocked = True
                            break

                        if future.done():
                            break

                        sleep(0.05)

                    assert blocked is True
                    assert future.done() is False

                    refund_count = observer.scalar(
                        select(func.count(Refund.id)).where(Refund.order_id == order_id)
                    )

                    assert refund_count == 0

                    observer.rollback()

            finally:
                lock_db.rollback()

            result = future.result(timeout=30)

        assert result.success is True
        assert result.executed is True
        assert result.already_executed is False

        assert result.action_id == action_id
        assert result.action_status == "executed"
        assert result.order_number == order_number
        assert result.order_status == "processing"

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            stored_order = db.get(Order, order_id)
            stored_action = db.get(PendingAction, action_id)

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.confirmed_at is not None
            assert stored_action.action_data["action_performed"] is True

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            refund = refunds[0]

            assert refund.status == "processing"
            assert refund.amount == Decimal("1299.00")
            assert refund.currency == "INR"

            assert stored_action.action_data["refund_id"] == refund.id

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            audit = audits[0]

            assert audit.outcome == "executed"
            assert audit.action_performed is True

            assert audit.details["refund_id"] == refund.id
            assert audit.details["refund_number"] == refund.refund_number

            db.rollback()

    finally:
        if lock_db is not None:
            lock_db.rollback()
            lock_db.close()

        if setup_committed:
            with SessionLocal() as db:
                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()
