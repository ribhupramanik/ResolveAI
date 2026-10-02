from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.tools.order_lookup import get_order

CANCELLABLE_STATUSES = {
    "processing",
}


NON_CANCELLABLE_REASONS = {
    "shipped": ("The order has already shipped."),
    "delivered": ("The order has already been delivered."),
    "cancelled": ("The order is already cancelled."),
    "canceled": ("The order is already cancelled."),
}


@dataclass(frozen=True)
class CancellationEligibilityResult:
    found: bool
    order_number: str

    status: str | None = None
    eligible: bool | None = None
    reason: str | None = None

    requires_confirmation: bool = False
    action_performed: bool = False


def check_cancellation_eligibility(
    db: Session,
    order_number: str,
) -> CancellationEligibilityResult:

    order = get_order(
        db,
        order_number,
    )

    if not order.found:
        return CancellationEligibilityResult(
            found=False,
            order_number=order.order_number,
            reason="Order not found.",
        )

    normalized_status = order.status.strip().lower() if order.status else ""

    if normalized_status in CANCELLABLE_STATUSES:
        return CancellationEligibilityResult(
            found=True,
            order_number=order.order_number,
            status=order.status,
            eligible=True,
            reason=("The order is still processing and is eligible for cancellation."),
            requires_confirmation=True,
            action_performed=False,
        )

    reason = NON_CANCELLABLE_REASONS.get(
        normalized_status,
        ("The current order status is not eligible for cancellation."),
    )

    return CancellationEligibilityResult(
        found=True,
        order_number=order.order_number,
        status=order.status,
        eligible=False,
        reason=reason,
        requires_confirmation=False,
        action_performed=False,
    )
