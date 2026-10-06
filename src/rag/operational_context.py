from dataclasses import dataclass

from src.tools.base import ToolResult


@dataclass(frozen=True)
class OperationalContext:
    context: str
    tool_used: bool
    tool_name: str | None
    tool_success: bool | None

    tool_results: tuple[ToolResult, ...] = ()


def build_operational_context(
    result: ToolResult | list[ToolResult] | None,
) -> OperationalContext:

    if result is None or result == []:
        return OperationalContext(
            context=("No operational tool was used for this request."),
            tool_used=False,
            tool_name=None,
            tool_success=None,
            tool_results=(),
        )

    if isinstance(result, ToolResult):
        results = [result]
    else:
        results = result

    context_blocks = []

    for item in results:
        if not item.success:
            context_blocks.append(
                f"Tool: {item.tool_name}\n"
                "Tool status: failed\n"
                f"Data: {item.data}\n"
                f"Error: {item.error}"
            )
            continue

        data_lines = [
            f"- {key}: {value}" for key, value in item.data.items() if value is not None
        ]

        context_blocks.append(
            f"Tool: {item.tool_name}\n"
            "Tool status: success\n"
            "Authoritative operational data:\n" + "\n".join(data_lines)
        )

    tool_results = tuple(results)

    if len(results) == 1:
        only_result = results[0]

        return OperationalContext(
            context=context_blocks[0],
            tool_used=True,
            tool_name=only_result.tool_name,
            tool_success=only_result.success,
            tool_results=tool_results,
        )

    return OperationalContext(
        context="\n\n".join(context_blocks),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )
