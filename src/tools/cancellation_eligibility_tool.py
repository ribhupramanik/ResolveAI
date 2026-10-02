from src.db.database import SessionLocal
from src.tools.base import ToolResult
from src.tools.cancellation_eligibility import (
    check_cancellation_eligibility,
)


class CancellationEligibilityTool:
    name = "check_cancellation_eligibility"

    def execute(
        self,
        order_number: str,
    ) -> ToolResult:

        db = SessionLocal()

        try:
            result = check_cancellation_eligibility(
                db,
                order_number,
            )

            if not result.found:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    data={
                        "order_number": (result.order_number),
                        "found": False,
                    },
                    error="Order not found.",
                )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={
                    "found": True,
                    "order_number": (result.order_number),
                    "status": result.status,
                    "eligible": result.eligible,
                    "reason": result.reason,
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
                error=("Cancellation eligibility check failed."),
            )

        finally:
            db.close()
