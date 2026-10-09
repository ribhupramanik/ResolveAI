from src.db.database import SessionLocal
from src.tools.base import ToolResult
from src.tools.refund_eligibility import (
    check_refund_eligibility,
)


class RefundEligibilityTool:
    name = "check_refund_eligibility"

    def execute(
        self,
        order_number: str,
    ) -> ToolResult:

        db = None

        try:
            db = SessionLocal()

            result = check_refund_eligibility(
                db,
                order_number,
            )

            if not result.found:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    data={
                        "order_number": result.order_number,
                        "found": False,
                    },
                    error="Order not found.",
                )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={
                    "found": True,
                    "order_number": result.order_number,
                    "status": result.status,
                    "payment_status": (result.payment_status),
                    "eligible": result.eligible,
                    "reason_code": result.reason_code,
                    "reason": result.reason,
                    "refund_amount": (
                        str(result.refund_amount)
                        if result.refund_amount is not None
                        else None
                    ),
                    "currency": result.currency,
                    "requires_confirmation": (result.requires_confirmation),
                    "action_performed": (result.action_performed),
                },
            )

        except Exception:
            return ToolResult(
                tool_name=self.name,
                success=False,
                data={
                    "order_number": order_number,
                },
                error=("Refund eligibility check failed."),
            )

        finally:
            if db is not None:
                db.close()
