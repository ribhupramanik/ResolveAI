from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Order


@dataclass(frozen=True)
class OrderLookupResult:
    found: bool
    order_number: str

    customer_name: str | None = None
    status: str | None = None
    payment_status: str | None = None

    total_amount: Decimal | None = None
    currency: str | None = None

    carrier: str | None = None
    tracking_number: str | None = None

    estimated_delivery: date | None = None


def get_order(
    db: Session,
    order_number: str,
) -> OrderLookupResult:

    normalized_order_number = (
        order_number.strip().upper()
    )

    statement = (
        select(Order)
        .where(
            Order.order_number
            == normalized_order_number
        )
    )

    order = db.scalar(statement)

    if order is None:
        return OrderLookupResult(
            found=False,
            order_number=(
                normalized_order_number
            ),
        )

    return OrderLookupResult(
        found=True,
        order_number=order.order_number,
        customer_name=order.customer.name,
        status=order.status,
        payment_status=(
            order.payment_status
        ),
        total_amount=order.total_amount,
        currency=order.currency,
        carrier=order.carrier,
        tracking_number=(
            order.tracking_number
        ),
        estimated_delivery=(
            order.estimated_delivery
        ),
    )