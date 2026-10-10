from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select, text

from src.db.database import SessionLocal, engine
from src.db.models import (
    Conversation,
    Customer,
    Order,
    PendingAction,
    Refund,
)
from src.services.pending_action_integration import (
    maybe_create_pending_refund,
)
from src.services.pending_action_service import (
    PendingActionService,
)


def test_eligible_refund_pending_action_persists_in_postgres():

    # Never use the development database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            # Verify the actual PostgreSQL connection.
            database_name = db.execute(text("SELECT current_database()")).scalar_one()

            assert database_name == "resolveai_test"

            suffix = uuid4().hex

            # Create a temporary conversation.
            conversation = Conversation(
                title="Refund PendingAction Test",
            )

            # Create a temporary customer.
            customer = Customer(
                customer_code=f"TST-{suffix[:20]}",
                name="Refund PendingAction Test",
                email=f"pending-refund-{suffix}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            # Create a temporary paid order.
            order_number = f"ORD-{uuid4().int % 10**18:018d}"

            order = Order(
                order_number=order_number,
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

            # Verify no refund exists initially.
            refund_count_before = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order_id)
            )

            assert refund_count_before == 0

            # Simulate a successful eligibility result.
            result = SimpleNamespace(
                used_fallback=False,
                tool_used=True,
                tool_name="check_refund_eligibility",
                tool_success=True,
                tool_data={
                    "found": True,
                    "order_number": order_number,
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

            # Execute the real integration.
            pending_action = maybe_create_pending_refund(
                db=db,
                conversation_id=conversation.id,
                result=result,
            )

            assert pending_action is not None

            action_id = pending_action.id

            # Reload from PostgreSQL rather than relying
            # only on the in-memory ORM object.
            db.flush()
            db.expire_all()

            saved_action = db.get(
                PendingAction,
                action_id,
            )

            assert saved_action is not None

            assert saved_action.conversation_id == (conversation.id)

            assert saved_action.action_type == ("initiate_refund")

            assert saved_action.target_type == "order"

            assert saved_action.target_identifier == (order_number)

            assert saved_action.status == "pending"

            assert saved_action.confirmed_at is None

            # Verify the persisted JSONB snapshot.
            action_data = saved_action.action_data

            assert action_data["order_status"] == ("processing")

            assert action_data["payment_status"] == ("paid")

            assert action_data["refund_amount"] == ("1299.00")

            assert action_data["currency"] == "INR"

            assert action_data["eligible"] is True

            assert action_data["requires_confirmation"] is True

            assert action_data["action_performed"] is False

            # Creating a PendingAction must not
            # create an actual refund.
            refund_count_after = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order_id)
            )

            assert refund_count_after == 0

        finally:
            # Roll back every temporary database record.
            db.rollback()


def test_refund_supersedes_existing_pending_cancellation_in_postgres():

    # Protect the development database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            database_name = db.execute(text("SELECT current_database()")).scalar_one()

            assert database_name == "resolveai_test"

            suffix = uuid4().hex

            # Create temporary conversation and customer.
            conversation = Conversation(
                title="Refund Superseding Test",
            )

            customer = Customer(
                customer_code=f"TST-{suffix[:20]}",
                name="Refund Superseding Test",
                email=f"refund-supersede-{suffix}@example.com",
            )

            db.add_all([conversation, customer])
            db.flush()

            # Create a temporary paid order.
            order_number = f"ORD-{uuid4().int % 10**18:018d}"

            order = Order(
                order_number=order_number,
                customer_id=customer.id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            # STEP 1: Create an existing cancellation PendingAction.
            service = PendingActionService(db)

            cancellation_action = service.create_pending_action(
                conversation_id=conversation.id,
                action_type="cancel_order",
                target_type="order",
                target_identifier=order_number,
                action_data={
                    "eligible": True,
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            assert cancellation_action.status == "pending"

            cancellation_action_id = cancellation_action.id

            # STEP 2: Simulate successful refund eligibility.
            result = SimpleNamespace(
                used_fallback=False,
                tool_used=True,
                tool_name="check_refund_eligibility",
                tool_success=True,
                tool_data={
                    "found": True,
                    "order_number": order_number,
                    "status": "processing",
                    "payment_status": "paid",
                    "eligible": True,
                    "reason_code": "ELIGIBLE",
                    "refund_amount": "1299.00",
                    "currency": "INR",
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            # STEP 3: Create the refund PendingAction.
            refund_action = maybe_create_pending_refund(
                db=db,
                conversation_id=conversation.id,
                result=result,
            )

            assert refund_action is not None

            refund_action_id = refund_action.id

            # STEP 4: Reload persisted records.
            db.flush()
            db.expire_all()

            saved_cancellation = db.get(
                PendingAction,
                cancellation_action_id,
            )

            saved_refund = db.get(
                PendingAction,
                refund_action_id,
            )

            # Previous cancellation must be superseded.
            assert saved_cancellation.status == "superseded"

            assert saved_cancellation.action_type == ("cancel_order")

            # New refund must remain pending.
            assert saved_refund.status == "pending"

            assert saved_refund.action_type == ("initiate_refund")

            assert saved_refund.target_identifier == (order_number)

            assert saved_refund.confirmed_at is None

            # Only one pending action should remain
            # in this conversation.
            pending_count = db.scalar(
                select(func.count(PendingAction.id)).where(
                    PendingAction.conversation_id == conversation.id,
                    PendingAction.status == "pending",
                )
            )

            assert pending_count == 1

            # Neither action should initiate a refund.
            refund_count = db.scalar(
                select(func.count(Refund.id)).where(Refund.order_id == order.id)
            )

            assert refund_count == 0

        finally:
            # Roll back all temporary test records.
            db.rollback()
