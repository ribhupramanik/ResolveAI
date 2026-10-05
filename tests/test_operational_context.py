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

    context = build_operational_context(results)

    assert context.tool_used is True
    assert context.tool_name is None
    assert context.tool_success is None

    assert "Tool: get_order" in context.context
    assert "status: delivered" in context.context

    assert "Tool: get_refund_status" in context.context
    assert "refund_number: REF-10003" in context.context
    assert "status: processing" in context.context
    assert "amount: 3899.00" in context.context

    get_order_position = context.context.index("Tool: get_order")
    refund_position = context.context.index("Tool: get_refund_status")

    assert get_order_position < refund_position


def test_single_success_preserves_legacy_metadata():
    result = ToolResult(
        tool_name="get_order",
        success=True,
        data={
            "order_number": "ORD-10001",
            "status": "shipped",
        },
    )

    context = build_operational_context(result)

    assert context.tool_used is True
    assert context.tool_name == "get_order"
    assert context.tool_success is True

    assert "Tool: get_order" in context.context
    assert "Tool status: success" in context.context
    assert "order_number: ORD-10001" in context.context
    assert "status: shipped" in context.context


def test_single_failure_preserves_legacy_metadata():
    result = ToolResult(
        tool_name="get_refund_status",
        success=False,
        data={
            "order_number": "ORD-99999",
            "order_found": False,
            "refund_found": False,
        },
        error="Order not found.",
    )

    context = build_operational_context(result)

    assert context.tool_used is True
    assert context.tool_name == "get_refund_status"
    assert context.tool_success is False

    assert "Tool: get_refund_status" in context.context
    assert "Tool status: failed" in context.context
    assert "ORD-99999" in context.context
    assert "Error: Order not found." in context.context
