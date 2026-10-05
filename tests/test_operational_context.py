from src.rag.operational_context import (
    build_operational_context,
)
from src.tools.base import ToolResult

def test_multiple_tool_results_build_combined_context():
    results = [
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=True,
            data={
                "order_number": "ORD-10003",
                "refund_number": "REF-10003",
                "status": "processing",
                "amount": "3899.00",
                "currency": "INR",
            },
        ),
    ]

    context = build_operational_context(
        results
    )

    assert context.tool_used is True
    assert context.tool_name is None
    assert context.tool_success is None

    assert "Tool: get_order" in context.context
    assert "status: delivered" in context.context

    assert (
        "Tool: get_refund_status"
        in context.context
    )
    assert (
        "refund_number: REF-10003"
        in context.context
    )
    assert "status: processing" in context.context
    assert "amount: 3899.00" in context.context

    get_order_position = context.context.index(
        "Tool: get_order"
    )
    refund_position = context.context.index(
        "Tool: get_refund_status"
    )

    assert get_order_position < refund_position