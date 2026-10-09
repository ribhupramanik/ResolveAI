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
