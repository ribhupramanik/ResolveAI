from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal
from uuid import uuid4

import pytest
from src.tools.refund_status import (
    get_refund_status,
)

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


def create_order(
    db,
    *,
    suffix: str,
) -> Order:
    customer = Customer(
        customer_code=f"CUST-REFUND-{suffix}",
        name="Refund Status Customer",
        email=(f"refund-status-{suffix.lower()}@example.com"),
    )

    db.add(customer)
    db.flush()

    order = Order(
        order_number=f"ORD-{suffix}",
        customer_id=customer.id,
        status="cancelled",
        payment_status="refunded",
        total_amount=Decimal("1299.00"),
        currency="INR",
        shipping_address=("Refund status test address"),
    )

    db.add(order)
    db.flush()

    return order


def test_existing_refund_status_is_returned(
    db,
):
    suffix = str(uuid4().int % 10_000_000_000).zfill(10)

    order = create_order(
        db,
        suffix=suffix,
    )

    initiated_at = datetime(
        2026,
        10,
        1,
        10,
        30,
        tzinfo=timezone.utc,
    )

    refund = Refund(
        refund_number=f"REF-{suffix}",
        order_id=order.id,
        status="processing",
        amount=Decimal("1299.00"),
        currency="INR",
        initiated_at=initiated_at,
    )

    db.add(refund)
    db.flush()

    result = get_refund_status(
        db,
        order.order_number,
    )

    assert result.order_found is True
    assert result.refund_found is True

    assert result.order_number == (order.order_number)

    assert result.refund_number == (refund.refund_number)

    assert result.status == "processing"

    assert result.amount == Decimal("1299.00")

    assert result.currency == "INR"

    assert result.initiated_at == (initiated_at)

    assert result.completed_at is None
    assert result.failure_reason is None


def test_existing_order_without_refund(
    db,
):
    suffix = str(uuid4().int % 10_000_000_000).zfill(10)

    order = create_order(
        db,
        suffix=suffix,
    )

    result = get_refund_status(
        db,
        order.order_number,
    )

    assert result.order_found is True
    assert result.refund_found is False

    assert result.order_number == (order.order_number)

    assert result.refund_number is None
    assert result.status is None
    assert result.amount is None
    assert result.currency is None
    assert result.initiated_at is None
    assert result.completed_at is None
    assert result.failure_reason is None


def test_unknown_order_is_distinguished_from_no_refund(
    db,
):
    result = get_refund_status(
        db,
        "ORD-9999999999",
    )

    assert result.order_found is False
    assert result.refund_found is False

    assert result.order_number == "ORD-9999999999"

    assert result.refund_number is None
    assert result.status is None


def test_latest_refund_is_returned(
    db,
):
    suffix = str(uuid4().int % 10_000_000_000).zfill(10)

    order = create_order(
        db,
        suffix=suffix,
    )

    now = datetime.now(timezone.utc)

    older_refund = Refund(
        refund_number=(f"REF-OLD-{suffix}"),
        order_id=order.id,
        status="failed",
        amount=Decimal("1299.00"),
        currency="INR",
        initiated_at=(now - timedelta(days=2)),
        failure_reason=("Payment provider rejected refund."),
    )

    newer_refund = Refund(
        refund_number=(f"REF-NEW-{suffix}"),
        order_id=order.id,
        status="processing",
        amount=Decimal("1299.00"),
        currency="INR",
        initiated_at=now,
    )

    db.add_all(
        [
            older_refund,
            newer_refund,
        ]
    )

    db.flush()

    result = get_refund_status(
        db,
        order.order_number.lower(),
    )

    assert result.order_found is True
    assert result.refund_found is True

    assert result.order_number == (order.order_number)

    assert result.refund_number == (newer_refund.refund_number)

    assert result.status == "processing"
    assert result.failure_reason is None
