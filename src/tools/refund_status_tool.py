from src.db.database import SessionLocal
from src.tools.base import ToolResult
from src.tools.refund_status import (
    get_refund_status,
)


class RefundStatusTool:
    name = "get_refund_status"

    def execute(
        self,
        order_number: str,
    ) -> ToolResult:

        db = SessionLocal()

        try:
            result = get_refund_status(
                db,
                order_number,
            )

            if not result.order_found:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    data={
                        "order_found": False,
                        "refund_found": False,
                        "order_number": (
                            result.order_number
                        ),
                    },
                    error="Order not found.",
                )

            if not result.refund_found:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={
                        "order_found": True,
                        "refund_found": False,
                        "order_number": (
                            result.order_number
                        ),
                    },
                )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={
                    "order_found": True,
                    "refund_found": True,
                    "order_number": (
                        result.order_number
                    ),
                    "refund_number": (
                        result.refund_number
                    ),
                    "status": result.status,
                    "amount": (
                        str(result.amount)
                        if result.amount is not None
                        else None
                    ),
                    "currency": result.currency,
                    "initiated_at": (
                        result.initiated_at.isoformat()
                        if result.initiated_at
                        is not None
                        else None
                    ),
                    "completed_at": (
                        result.completed_at.isoformat()
                        if result.completed_at
                        is not None
                        else None
                    ),
                    "failure_reason": (
                        result.failure_reason
                    ),
                },
            )

        except Exception:
            return ToolResult(
                tool_name=self.name,
                success=False,
                data={
                    "order_number": order_number,
                },
                error=(
                    "Refund status lookup failed."
                ),
            )

        finally:
            db.close()