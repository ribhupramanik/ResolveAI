from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PendingAction

from src.services.pending_action_service import (
    CONFIRMED,
)


@dataclass(frozen=True)
class RefundExecutionResult:
    success: bool
    executed: bool
    already_executed: bool

    action_id: int | None
    action_status: str | None

    order_number: str | None
    order_status: str | None

    reason: str


class RefundExecutionService:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def execute(
        self,
        pending_action_id: int,
    ) -> RefundExecutionResult:
        """
        Execute a previously confirmed refund action.

        This service does not commit transactions.
        The caller owns the surrounding transaction.

        Actual refund initiation is not implemented yet.
        """

        # Lock the PendingAction before examining
        # its current state.
        action = self.db.scalar(
            select(PendingAction)
            .where(
                PendingAction.id == pending_action_id
            )
            .with_for_update()
        )

        # Case 1: PendingAction does not exist.
        if action is None:
            return RefundExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=None,
                action_status=None,
                order_number=None,
                order_status=None,
                reason="Pending action not found.",
            )

        order_number = (
            action.target_identifier.strip().upper()
        )

        # Case 2: The PendingAction must represent
        # a refund initiation for an order.
        if (
            action.action_type != "initiate_refund"
            or action.target_type != "order"
        ):
            return RefundExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=None,
                reason=(
                    "Pending action is not an "
                    "order refund initiation action."
                ),
            )

        # Case 3: Refund execution requires
        # explicit customer confirmation.
        if action.status != CONFIRMED:
            return RefundExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=None,
                reason="Refund has not been confirmed.",
            )

        # Actual refund execution will be implemented
        # in subsequent Stage 4C5 steps.
        #
        # For now, even confirmed refunds must
        # fail safely without changing the database.
        return RefundExecutionResult(
            success=False,
            executed=False,
            already_executed=False,
            action_id=action.id,
            action_status=action.status,
            order_number=order_number,
            order_status=None,
            reason="Refund execution is not implemented yet.",
        )