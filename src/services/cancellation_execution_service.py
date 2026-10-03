from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Order, PendingAction
from src.services.pending_action_service import (
    CONFIRMED,
    EXECUTED,
    INVALIDATED,
)

ELIGIBLE_ORDER_STATUS = "processing"
CANCELLED_ORDER_STATUS = "cancelled"


@dataclass(frozen=True)
class CancellationExecutionResult:
    success: bool
    executed: bool
    already_executed: bool

    action_id: int | None
    action_status: str | None

    order_number: str | None
    order_status: str | None

    reason: str


class CancellationExecutionService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def execute(
        self,
        pending_action_id: int,
    ) -> CancellationExecutionResult:
        """
        Execute a previously confirmed cancellation action.

        This method does not commit. The caller owns the
        surrounding transaction.
        """

        action = self.db.scalar(
            select(PendingAction)
            .where(PendingAction.id == pending_action_id)
            .with_for_update()
        )

        if action is None:
            return CancellationExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=None,
                action_status=None,
                order_number=None,
                order_status=None,
                reason="Pending action not found.",
            )

        order_number = action.target_identifier.strip().upper()

        if action.action_type != "cancel_order" or action.target_type != "order":
            return CancellationExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=None,
                reason=("Pending action is not an order cancellation action."),
            )

        # Idempotency:
        # Never perform the same action twice.
        if action.status == EXECUTED:
            order = self.db.scalar(
                select(Order)
                .where(Order.order_number == order_number)
                .with_for_update()
            )

            if order is None or order.status.strip().lower() != CANCELLED_ORDER_STATUS:
                raise RuntimeError(
                    "Executed cancellation action has inconsistent order state."
                )

            return CancellationExecutionResult(
                success=True,
                executed=False,
                already_executed=True,
                action_id=action.id,
                action_status=action.status,
                order_number=order.order_number,
                order_status=order.status,
                reason=("Cancellation was already executed."),
            )

        # Only explicit customer confirmation may reach
        # the mutation stage.
        if action.status != CONFIRMED:
            return CancellationExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=None,
                reason=("Cancellation has not been confirmed."),
            )

        action_data = dict(action.action_data or {})

        # Fail closed if the stored state contradicts
        # the confirmed status.
        if action_data.get("action_performed") is True:
            raise RuntimeError(
                "Confirmed pending action has an inconsistent performed state."
            )

        # Lock the order after locking the action.
        order = self.db.scalar(
            select(Order).where(Order.order_number == order_number).with_for_update()
        )

        if order is None:
            reason = "The target order no longer exists."

            action.status = INVALIDATED
            action.action_data = {
                **action_data,
                "action_performed": False,
                "execution_blocked_reason": reason,
            }

            self.db.flush()

            return CancellationExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=None,
                reason=reason,
            )

        current_status = order.status.strip().lower()

        # Re-check eligibility at execution time.
        if current_status != ELIGIBLE_ORDER_STATUS:
            reason = (
                "Order is no longer eligible for "
                f"cancellation because its current "
                f"status is '{order.status}'."
            )

            action.status = INVALIDATED
            action.action_data = {
                **action_data,
                "action_performed": False,
                "current_order_status": order.status,
                "execution_blocked_reason": reason,
            }

            self.db.flush()

            return CancellationExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order.order_number,
                order_status=order.status,
                reason=reason,
            )

        previous_status = order.status
        executed_at = datetime.now(timezone.utc)

        order.status = CANCELLED_ORDER_STATUS

        action.status = EXECUTED

        # Assign a new dict rather than mutating JSONB
        # in place so SQLAlchemy reliably detects it.
        action.action_data = {
            **action_data,
            "action_performed": True,
            "previous_order_status": previous_status,
            "final_order_status": (CANCELLED_ORDER_STATUS),
            "executed_at": executed_at.isoformat(),
        }

        self.db.flush()

        return CancellationExecutionResult(
            success=True,
            executed=True,
            already_executed=False,
            action_id=action.id,
            action_status=action.status,
            order_number=order.order_number,
            order_status=order.status,
            reason=("Order cancellation executed successfully."),
        )
