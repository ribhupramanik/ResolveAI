from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from src.db.database import SessionLocal, engine
from src.db.models import Customer, Order
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
