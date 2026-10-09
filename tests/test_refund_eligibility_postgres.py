from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from src.db.database import SessionLocal, engine
from src.db.models import Customer, Order, Refund
from src.tools.refund_eligibility import (
    check_refund_eligibility,
)


def test_refund_checks_use_test_database():

    # Check the configured SQLAlchemy engine first.
    assert engine.url.database == "resolveai_test"

    # Verify the actual PostgreSQL connection.
    with SessionLocal() as db:
        database_name = db.execute(text("SELECT current_database()")).scalar_one()

        assert database_name == "resolveai_test"


def test_paid_processing_order_is_eligible_in_postgres():

    # Never modify the development database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            # Verify the actual connected database.
            database_name = db.execute(text("SELECT current_database()")).scalar_one()

            assert database_name == "resolveai_test"

            # Unique identifiers prevent collisions
            # with existing test records.
            suffix = uuid4().hex

            customer = Customer(
                customer_code=f"TST-{suffix[:20]}",
                name="Refund Eligibility Test",
                email=f"refund-test-{suffix}@example.com",
            )

            db.add(customer)
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

            # Execute the real eligibility function.
            result = check_refund_eligibility(
                db,
                order.order_number,
            )

            assert result.found is True
            assert result.order_number == order.order_number

            assert result.status == "processing"
            assert result.payment_status == "paid"

            assert result.eligible is True
            assert result.reason_code == "ELIGIBLE"

            assert result.refund_amount == Decimal("1299.00")
            assert result.currency == "INR"

            assert result.requires_confirmation is True
            assert result.action_performed is False

        finally:
            # Never persist integration-test data.
            db.rollback()


def test_existing_processing_refund_blocks_new_refund_in_postgres():

    # Never modify the development database.
    assert engine.url.database == "resolveai_test"

    with SessionLocal() as db:
        try:
            # Verify the actual database connection.
            database_name = db.execute(text("SELECT current_database()")).scalar_one()

            assert database_name == "resolveai_test"

            # Create unique test identifiers.
            suffix = uuid4().hex

            customer = Customer(
                customer_code=f"TST-{suffix[:20]}",
                name="Refund Processing Test",
                email=f"refund-processing-{suffix}@example.com",
            )

            db.add(customer)
            db.flush()

            order = Order(
                order_number=(f"ORD-{uuid4().int % 10**18:018d}"),
                customer_id=customer.id,
                status="delivered",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            # Create an existing processing refund.
            refund = Refund(
                refund_number=f"REF-TST-{uuid4().hex[:20]}",
                order_id=order.id,
                status="processing",
                amount=Decimal("1299.00"),
                currency="INR",
                initiated_at=datetime.now(timezone.utc),
                completed_at=None,
                failure_reason=None,
            )

            db.add(refund)
            db.flush()

            # Execute real refund eligibility logic.
            result = check_refund_eligibility(
                db,
                order.order_number,
            )

            assert result.found is True
            assert result.order_number == order.order_number

            assert result.status == "delivered"
            assert result.payment_status == "paid"

            assert result.eligible is False

            assert result.reason_code == ("REFUND_ALREADY_PROCESSING")

            assert result.reason == (
                "A refund is already being processed for this order."
            )

            assert result.refund_amount is None
            assert result.currency is None

            assert result.requires_confirmation is False
            assert result.action_performed is False

        finally:
            # Remove all temporary test records.
            db.rollback()
