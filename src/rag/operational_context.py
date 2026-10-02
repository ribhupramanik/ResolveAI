from dataclasses import dataclass

from src.tools.base import ToolResult


@dataclass(frozen=True)
class OperationalContext:
    context: str
    tool_used: bool
    tool_name: str | None
    tool_success: bool | None


def build_operational_context(
    result: ToolResult | None,
) -> OperationalContext:

    if result is None:
        return OperationalContext(
            context=(
                "No operational tool was used "
                "for this request."
            ),
            tool_used=False,
            tool_name=None,
            tool_success=None,
        )

    if not result.success:
        return OperationalContext(
            context=(
                f"Tool: {result.tool_name}\n"
                "Tool status: failed\n"
                f"Data: {result.data}\n"
                f"Error: {result.error}"
            ),
            tool_used=True,
            tool_name=result.tool_name,
            tool_success=False,
        )

    data_lines = [
        f"- {key}: {value}"
        for key, value in result.data.items()
        if value is not None
    ]

    return OperationalContext(
        context=(
            f"Tool: {result.tool_name}\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            + "\n".join(data_lines)
        ),
        tool_used=True,
        tool_name=result.tool_name,
        tool_success=True,
    )