import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import (
    ActionExecutionAudit,
    Order,
    PendingAction,
    Refund,
)
from src.services.pending_action_service import (
    CONFIRMED,
    EXECUTED,
    INVALIDATED,
)
from src.tools.refund_eligibility import (
    check_refund_eligibility,
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

    def _invalidate_action(
        self,
        *,
        action: PendingAction,
        order: Order | None,
        reason: str,
    ) -> RefundExecutionResult:
        """
        Invalidate a confirmed refund action when
        execution-time validation fails.

        Records the invalidation and its audit
        within the caller's transaction.

        This method never creates a Refund record
        and never commits the transaction.
        """

        order_number = action.target_identifier.strip().upper()

        current_order_status = order.status if order is not None else None

        action.status = INVALIDATED
        action.action_data = {
            **dict(action.action_data or {}),
            "action_performed": False,
            "current_order_status": current_order_status,
            "execution_blocked_reason": reason,
        }

        audit = ActionExecutionAudit(
            pending_action_id=action.id,
            conversation_id=action.conversation_id,
            action_type=action.action_type,
            target_type=action.target_type,
            target_identifier=order_number,
            outcome=INVALIDATED,
            action_performed=False,
            previous_target_status=current_order_status,
            final_target_status=current_order_status,
            reason=reason,
            details={
                "blocked_stage": "execution_revalidation",
                "order_found": order is not None,
            },
        )

        self.db.add(audit)

        self.db.flush()

        return RefundExecutionResult(
            success=False,
            executed=False,
            already_executed=False,
            action_id=action.id,
            action_status=action.status,
            order_number=order_number,
            order_status=current_order_status,
            reason=reason,
        )

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
            .where(PendingAction.id == pending_action_id)
            .with_for_update()
        )

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

        order_number = action.target_identifier.strip().upper()

        if action.action_type != "initiate_refund" or action.target_type != "order":
            return RefundExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=None,
                reason=("Pending action is not an order refund initiation action."),
            )


        if action.status == EXECUTED:

            # Read the execution metadata.
            action_data = (
                action.action_data
                if isinstance(action.action_data, dict)
                else {}
            )

            refund_id = action_data.get("refund_id")
            refund_number = action_data.get("refund_number")

            # Lock the authoritative order.
            #
            # Maintain the established lock ordering:
            # PendingAction -> Order.

            order = self.db.scalar(
                select(Order)
                .where(Order.order_number == order_number)
                .with_for_update()
            )

            # Retrieve the refund recorded by
            # the original execution.
            #
            # Reject invalid identifiers rather than
            # trusting the JSONB metadata.

            refund = None

            if type(refund_id) is int and refund_id > 0:
                refund = self.db.get(
                    Refund,
                    refund_id,
                )

            # Retrieve the original execution audit.
            audit = self.db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id
                    == action.id
                )
            )

            audit_details = (
                audit.details
                if audit is not None
                and isinstance(audit.details, dict)
                else {}
            )

            # Read the originally confirmed amount.
            # Do not compare it with the current order
            # total because the order may have changed
            # AFTER the refund was initiated.

            recorded_amount = None

            raw_amount = action_data.get("refund_amount")

            if isinstance(raw_amount, str):
                try:
                    recorded_amount = Decimal(raw_amount)
                except InvalidOperation:
                    pass


            records_consistent = (
                action.confirmed_at is not None
                and action_data.get("action_performed") is True
                and action_data.get("eligible") is True
                and action_data.get("requires_confirmation") is True
                and order is not None
                and refund is not None
                and audit is not None
                and recorded_amount is not None
                and recorded_amount.is_finite()
                and recorded_amount > 0
                and isinstance(refund_number, str)
                and refund.order_id == order.id
                and refund.refund_number == refund_number
                and refund.amount == recorded_amount
                and refund.currency == action_data.get("currency")
                and audit.outcome == EXECUTED
                and audit.action_performed is True
                and audit.conversation_id == action.conversation_id
                and audit.action_type == "initiate_refund"
                and audit.target_type == "order"
                and audit.target_identifier == order_number
                and audit_details.get("refund_id") == refund_id
                and audit_details.get("refund_number") == refund_number
            )


            if not records_consistent:
                return RefundExecutionResult(
                    success=False,
                    executed=False,
                    already_executed=False,
                    action_id=action.id,
                    action_status=action.status,
                    order_number=order_number,
                    order_status=(
                        order.status if order is not None else None
                    ),
                    reason=(
                        "Previously executed refund action "
                        "has inconsistent records."
                    ),
                )

            return RefundExecutionResult(
                success=True,
                executed=False,
                already_executed=True,
                action_id=action.id,
                action_status=EXECUTED,
                order_number=order_number,
                order_status=order.status,
                reason="Refund initiation was already recorded.",
            )

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

        action_data = dict(action.action_data or {})

        def blocked_result(
            reason: str,
            order_status: str | None = None,
        ) -> RefundExecutionResult:
            return RefundExecutionResult(
                success=False,
                executed=False,
                already_executed=False,
                action_id=action.id,
                action_status=action.status,
                order_number=order_number,
                order_status=order_status,
                reason=reason,
            )

        if (
            action.confirmed_at is None
            or action_data.get("eligible") is not True
            or action_data.get("requires_confirmation") is not True
            or action_data.get("action_performed") is not False
        ):
            return blocked_result(
                "Refund action has invalid confirmation or eligibility data."
            )

        raw_amount = action_data.get("refund_amount")
        raw_currency = action_data.get("currency")

        if not isinstance(raw_amount, str) or not re.fullmatch(
            r"(?:0|[1-9]\d*)(?:\.\d{1,2})?",
            raw_amount,
        ):
            return blocked_result("Refund action contains an invalid amount.")

        try:
            snapshot_amount = Decimal(raw_amount)

        except InvalidOperation:
            return blocked_result("Refund action contains an invalid amount.")

        if not snapshot_amount.is_finite() or snapshot_amount <= 0:
            return blocked_result("Refund action contains an invalid amount.")

        if not isinstance(raw_currency, str) or not re.fullmatch(
            r"[A-Z]{3}",
            raw_currency,
        ):
            return blocked_result("Refund action contains an invalid currency.")

        snapshot_currency = raw_currency

        order = self.db.scalar(
            select(Order).where(Order.order_number == order_number).with_for_update()
        )

        if order is None:
            return blocked_result("The target order no longer exists.")

        eligibility = check_refund_eligibility(
            db=self.db,
            order_number=order_number,
        )

        if (
            eligibility.found is not True
            or eligibility.eligible is not True
            or eligibility.requires_confirmation is not True
            or eligibility.action_performed is not False
        ):
            reason = (
                eligibility.reason or "The order is no longer eligible for a refund."
            )

            return self._invalidate_action(
                action=action,
                order=order,
                reason=reason,
            )

        if (
            eligibility.refund_amount is None
            or snapshot_amount != order.total_amount
            or snapshot_amount != eligibility.refund_amount
        ):
            return self._invalidate_action(
                action=action,
                order=order,
                reason="Refund amount no longer matches the order.",
            )

        current_currency = order.currency.strip().upper()

        if (
            snapshot_currency != current_currency
            or eligibility.currency is None
            or snapshot_currency
            != eligibility.currency.strip().upper()
        ):
            return self._invalidate_action(
                action=action,
                order=order,
                reason="Refund currency no longer matches the order.",
            )

        initiated_at = datetime.now(UTC)

        refund = Refund(
            refund_number=f"REF-{uuid4().hex.upper()}",
            order_id=order.id,
            status="processing",
            amount=snapshot_amount,
            currency=snapshot_currency,
            initiated_at=initiated_at,
            completed_at=None,
            failure_reason=None,
        )

        self.db.add(refund)

        self.db.flush()

        action.status = EXECUTED

        action.action_data = {
            **action_data,
            "action_performed": True,
            "refund_id": refund.id,
            "refund_number": refund.refund_number,
            "executed_at": initiated_at.isoformat(),
        }

        success_reason = "Refund initiation recorded successfully."

        audit = ActionExecutionAudit(
            pending_action_id=action.id,
            conversation_id=action.conversation_id,
            action_type=action.action_type,
            target_type=action.target_type,
            target_identifier=order_number,
            outcome=EXECUTED,
            action_performed=True,
            previous_target_status=order.status,
            final_target_status=order.status,
            reason=success_reason,
            details={
                "refund_id": refund.id,
                "refund_number": refund.refund_number,
                "refund_amount": str(refund.amount),
                "currency": refund.currency,
                "refund_status": "processing",
                "initiated_at": initiated_at.isoformat(),
            },
        )

        self.db.add(audit)

        self.db.flush()

        return RefundExecutionResult(
            success=True,
            executed=True,
            already_executed=False,
            action_id=action.id,
            action_status=action.status,
            order_number=order.order_number,
            order_status=order.status,
            reason=success_reason,
        )


