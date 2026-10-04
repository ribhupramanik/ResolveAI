from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import (
    Order,
    Refund,
)


@dataclass(frozen=True)
class RefundStatusResult:
    order_found: bool
    refund_found: bool
    order_number: str

    refund_number: str | None = None
    status: str | None = None

    amount: Decimal | None = None
    currency: str | None = None

    initiated_at: datetime | None = None
    completed_at: datetime | None = None

    failure_reason: str | None = None


def get_refund_status(
    db: Session,
    order_number: str,
) -> RefundStatusResult:

    normalized_order_number = order_number.strip().upper()

    order_statement = select(Order).where(Order.order_number == normalized_order_number)

    order = db.scalar(order_statement)

    if order is None:
        return RefundStatusResult(
            order_found=False,
            refund_found=False,
            order_number=(normalized_order_number),
        )

    refund_statement = (
        select(Refund)
        .where(Refund.order_id == order.id)
        .order_by(
            Refund.initiated_at.desc(),
            Refund.id.desc(),
        )
    )

    refund = db.scalars(refund_statement).first()

    if refund is None:
        return RefundStatusResult(
            order_found=True,
            refund_found=False,
            order_number=order.order_number,
        )

    return RefundStatusResult(
        order_found=True,
        refund_found=True,
        order_number=order.order_number,
        refund_number=(refund.refund_number),
        status=refund.status,
        amount=refund.amount,
        currency=refund.currency,
        initiated_at=refund.initiated_at,
        completed_at=refund.completed_at,
        failure_reason=(refund.failure_reason),
    )
