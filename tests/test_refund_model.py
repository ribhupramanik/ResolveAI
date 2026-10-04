from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.db.database import SessionLocal
from src.db.models import (
    Customer,
    Order,
    Refund,
)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_refund_can_be_persisted_for_order(
    db,
):
    token = uuid4().hex[:10].upper()

    customer = Customer(
        customer_code=f"CUST-REF-{token}",
        name="Refund Test Customer",
        email=(f"refund-{token.lower()}@example.com"),
    )

    db.add(customer)
    db.flush()

    order = Order(
        order_number=f"ORD-{uuid4().int % 10_000_000_000:010d}",
        customer_id=customer.id,
        status="cancelled",
        payment_status="refunded",
        total_amount=Decimal("1299.00"),
        currency="INR",
        shipping_address="Refund test address",
    )

    db.add(order)
    db.flush()

    initiated_at = datetime.now(timezone.utc)

    refund = Refund(
        refund_number=f"REF-{token}",
        order_id=order.id,
        status="processing",
        amount=Decimal("1299.00"),
        currency="INR",
        initiated_at=initiated_at,
    )

    db.add(refund)
    db.flush()

    assert refund.id is not None

    assert refund.refund_number == (f"REF-{token}")

    assert refund.order_id == order.id
    assert refund.status == "processing"

    assert refund.amount == Decimal("1299.00")

    assert refund.currency == "INR"

    assert refund.completed_at is None
    assert refund.failure_reason is None

    assert refund.order.id == order.id
    assert refund.order.order_number == (order.order_number)
