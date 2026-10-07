from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.tools.order_lookup import get_order


@dataclass(frozen=True)
class RefundEligibilityResult:
    found: bool
    order_number: str

    eligible: bool | None = None

    reason_code: str | None = None
    reason: str | None = None

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
            eligible=False,
            reason_code="ORDER_NOT_PAID",
            reason="The order has not been paid.",
            requires_confirmation=False,
            action_performed=False,
        )

    raise NotImplementedError(
        "Remaining refund eligibility rules are not implemented yet."
    )
