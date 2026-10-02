from src.db.database import SessionLocal
from src.tools.base import ToolResult
from src.tools.order_lookup import get_order


class OrderLookupTool:
    name = "get_order"

    def execute(
        self,
        order_number: str,
    ) -> ToolResult:

        db = SessionLocal()

        try:
            result = get_order(
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
                    "customer_name": result.customer_name,
                    "status": result.status,
                    "payment_status": result.payment_status,
                    "total_amount": (
                        str(result.total_amount)
                        if result.total_amount is not None
                        else None
                    ),
                    "currency": result.currency,
                    "carrier": result.carrier,
                    "tracking_number": result.tracking_number,
                    "estimated_delivery": (
                        result.estimated_delivery.isoformat()
                        if result.estimated_delivery is not None
                        else None
                    ),
                },
            )

        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                data={
                    "order_number": order_number,
                },
                error=str(exc),
            )

        finally:
            db.close()
