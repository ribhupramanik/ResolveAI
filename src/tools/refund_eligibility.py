from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Order, Refund
from src.tools.order_lookup import get_order

REFUND_ELIGIBLE_ORDER_STATUSES = {
    "processing",
    "delivered",
}


@dataclass(frozen=True)
class RefundEligibilityResult:
    found: bool
    order_number: str

    status: str | None = None
    payment_status: str | None = None

    eligible: bool | None = None

    reason_code: str | None = None
    reason: str | None = None

    refund_amount: Decimal | None = None
    currency: str | None = None

    requires_confirmation: bool = False
    action_performed: bool = False


def check_refund_eligibility(
    db: Session,
    order_number: str,
) -> RefundEligibilityResult:

    order = get_order(
        db,
        order_number,
    )

    if not order.found:
        return RefundEligibilityResult(
            found=False,
            order_number=order.order_number,
            eligible=None,
            reason_code="ORDER_NOT_FOUND",
            reason="Order not found.",
            requires_confirmation=False,
            action_performed=False,
        )

    normalized_payment_status = (
        order.payment_status.strip().lower() if order.payment_status else ""
    )

    if normalized_payment_status != "paid":
        return RefundEligibilityResult(
            found=True,
            order_number=order.order_number,
            status=order.status,
            payment_status=order.payment_status,
            eligible=False,
            reason_code="ORDER_NOT_PAID",
            reason="The order has not been paid.",
            requires_confirmation=False,
            action_performed=False,
        )

    refund_status_statement = (
        select(Refund.status)
        .join(
            Order,
            Refund.order_id == Order.id,
        )
        .where(
            Order.order_number == order.order_number,
        )
    )

    refund_statuses = db.scalars(refund_status_statement).all()

    normalized_status = order.status.strip().lower() if order.status else ""

    if normalized_status == "shipped":
        return RefundEligibilityResult(
            found=True,
            order_number=order.order_number,
            status=order.status,
            payment_status=order.payment_status,
            eligible=False,
            reason_code="ORDER_SHIPPED",
            reason=(
                "The order has already shipped and is not eligible for a direct refund."
            ),
            requires_confirmation=False,
            action_performed=False,
        )

    refund_status_statement = (
        select(Refund.status)
        .join(
            Order,
            Refund.order_id == Order.id,
        )
        .where(
            Order.order_number == order.order_number,
        )
    )

    refund_statuses = db.scalars(refund_status_statement).all()

    if normalized_status in REFUND_ELIGIBLE_ORDER_STATUSES and not refund_statuses:
        return RefundEligibilityResult(
            found=True,
            order_number=order.order_number,
            status=order.status,
            payment_status=order.payment_status,
            eligible=True,
            reason_code="ELIGIBLE",
            reason=("The order is eligible for a full refund."),
            refund_amount=order.total_amount,
            currency=order.currency,
            requires_confirmation=True,
            action_performed=False,
        )

    raise NotImplementedError(
        "Remaining refund eligibility rules are not implemented yet."
    )
