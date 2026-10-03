import re

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

    if (
        result.tool_name
        != "check_cancellation_eligibility"
    ):
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

    if (
        data.get("requires_confirmation")
        is not True
    ):
        return None

    if data.get("action_performed") is not False:
        return None

    order_number = data.get("order_number")

    if not isinstance(order_number, str):
        return None

    order_number = order_number.strip().upper()

    if not ORDER_NUMBER_PATTERN.fullmatch(
        order_number
    ):
        return None

    action_data = {
        "order_status": data.get("status"),
        "eligible": True,
        "requires_confirmation": True,
        "action_performed": False,
    }

    reason = data.get("reason")

    if isinstance(reason, str) and reason.strip():
        action_data["eligibility_reason"] = (
            reason.strip()
        )

    service = PendingActionService(db)

    return service.create_pending_action(
        conversation_id=conversation_id,
        action_type="cancel_order",
        target_type="order",
        target_identifier=order_number,
        action_data=action_data,
    )