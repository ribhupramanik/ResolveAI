import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from src.db.models import PendingAction
from src.rag.pipeline import RAGResult
from src.services.pending_action_service import (
    PendingActionService,
)

ORDER_NUMBER_PATTERN = re.compile(
    r"^ORD-\d+$",
    re.IGNORECASE,
)


def maybe_create_pending_cancellation(
    db: Session,
    conversation_id: int,
    result: RAGResult,
) -> PendingAction | None:
    """
    Create a pending cancellation action only when a
    successful cancellation-eligibility tool execution
    proves that explicit confirmation is required.

    This function never modifies the order itself.
    """

    if result.used_fallback:
        return None

    if not result.tool_used:
        return None

    if result.tool_name != "check_cancellation_eligibility":
        return None

    if result.tool_success is not True:
        return None

    data = result.tool_data

    if not isinstance(data, dict):
        return None

    if data.get("found") is not True:
        return None

    if data.get("eligible") is not True:
        return None

    if data.get("requires_confirmation") is not True:
        return None

    if data.get("action_performed") is not False:
        return None

    order_number = data.get("order_number")

    if not isinstance(order_number, str):
        return None

    order_number = order_number.strip().upper()

    if not ORDER_NUMBER_PATTERN.fullmatch(order_number):
        return None

    action_data = {
        "order_status": data.get("status"),
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    reason = data.get("reason")

    if isinstance(reason, str) and reason.strip():
        action_data["eligibility_reason"] = reason.strip()

    service = PendingActionService(db)

    return service.create_pending_action(
        conversation_id=conversation_id,
        action_type="cancel_order",
        target_type="order",
        target_identifier=order_number,
        action_data=action_data,
    )


def maybe_create_pending_refund(
    db: Session,
    conversation_id: int,
    result: RAGResult,
) -> PendingAction | None:
    """
    Create a pending refund action only when a successful
    refund eligibility check requires confirmation.

    This function never initiates a refund.
    """

    # 1. Reject fallback responses.
    if result.used_fallback:
        return None

    # 2. Require a successful refund eligibility tool.
    if not result.tool_used:
        return None

    if result.tool_name != "check_refund_eligibility":
        return None

    if result.tool_success is not True:
        return None

    # 3. Validate eligibility data.
    data = result.tool_data

    if not isinstance(data, dict):
        return None

    if data.get("found") is not True:
        return None

    if data.get("eligible") is not True:
        return None

    if data.get("requires_confirmation") is not True:
        return None

    if data.get("action_performed") is not False:
        return None

    # 4. Validate the order number.
    order_number = data.get("order_number")

    if not isinstance(order_number, str):
        return None

    order_number = order_number.strip().upper()

    if not ORDER_NUMBER_PATTERN.fullmatch(order_number):
        return None

    # 5. Validate the financial snapshot.
    refund_amount = data.get("refund_amount")
    currency = data.get("currency")

    if not isinstance(refund_amount, str):
        return None

    refund_amount = refund_amount.strip()

    try:
        amount = Decimal(refund_amount)
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount <= 0:
        return None

    if not re.fullmatch(
        r"(?:0|[1-9]\d*)(?:\.\d{1,2})?",
        refund_amount,
    ):
        return None

    if not isinstance(currency, str):
        return None

    currency = currency.strip().upper()

    if not re.fullmatch(r"[A-Z]{3}", currency):
        return None

    # 6. Prepare the refund snapshot.
    action_data = {
        "order_status": data.get("status"),
        "payment_status": data.get("payment_status"),
        "refund_amount": refund_amount,
        "currency": currency,
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    reason = data.get("reason")

    if isinstance(reason, str) and reason.strip():
        action_data["eligibility_reason"] = reason.strip()

    # 7. Reuse the existing PendingAction service.
    service = PendingActionService(db)

    return service.create_pending_action(
        conversation_id=conversation_id,
        action_type="initiate_refund",
        target_type="order",
        target_identifier=order_number,
        action_data=action_data,
    )
