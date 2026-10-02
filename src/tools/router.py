import re

from src.rag.conversation import (
    ConversationTurn,
)

ORDER_NUMBER_PATTERN = re.compile(
    r"\bORD-\d+\b",
    re.IGNORECASE,
)


def extract_order_number(
    query: str,
    conversation_history: list[ConversationTurn] | None = None,
) -> str | None:

    current_match = ORDER_NUMBER_PATTERN.search(query)

    if current_match:
        return current_match.group(0).upper()

    history = conversation_history or []

    for turn in reversed(history):
        if turn.role != "user":
            continue

        match = ORDER_NUMBER_PATTERN.search(turn.content)

        if match:
            return match.group(0).upper()

    return None


from src.tools.base import (
    ToolResult,
)
from src.tools.order_lookup_tool import (
    OrderLookupTool,
)


class ToolRouter:
    def __init__(
        self,
        order_lookup_tool: OrderLookupTool | None = None,
    ):
        self.order_lookup_tool = (
            order_lookup_tool if order_lookup_tool is not None else OrderLookupTool()
        )

    def run(
        self,
        query: str,
        conversation_history: list[ConversationTurn] | None = None,
    ) -> ToolResult | None:

        order_number = extract_order_number(
            query,
            conversation_history,
        )

        if order_number is None:
            return None

        return self.order_lookup_tool.execute(order_number)
