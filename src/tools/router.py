import re

from src.rag.conversation import (
    ConversationTurn,
)
from src.tools.base import (
    ToolResult,
)
from src.tools.cancellation_eligibility_tool import (
    CancellationEligibilityTool,
)
from src.tools.order_lookup_tool import (
    OrderLookupTool,
)

ORDER_NUMBER_PATTERN = re.compile(
    r"\bORD-\d+\b",
    re.IGNORECASE,
)


CANCELLATION_REQUEST_PATTERNS = [
    re.compile(
        r"\b(?:can|could|may)\s+"
        r"(?:i|we)\s+cancel\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)\s+"
        r"(?:want|need|would\s+like)\s+"
        r"to\s+cancel\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcancel\s+"
        r"(?:(?:my|the|this)\s+)?"
        r"order\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\border\s+cancellation\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcan\s+"
        r"(?:this\s+)?order\b"
        r".*?"
        r"\bbe\s+cancel(?:led|ed)?\b",
        re.IGNORECASE,
    ),
]


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


def is_cancellation_request(
    query: str,
) -> bool:

    return any(pattern.search(query) for pattern in CANCELLATION_REQUEST_PATTERNS)


class ToolRouter:
    def __init__(
        self,
        order_lookup_tool: OrderLookupTool | None = None,
        cancellation_eligibility_tool: CancellationEligibilityTool | None = None,
    ):
        self.order_lookup_tool = (
            order_lookup_tool if order_lookup_tool is not None else OrderLookupTool()
        )

        self.cancellation_eligibility_tool = (
            cancellation_eligibility_tool
            if cancellation_eligibility_tool is not None
            else CancellationEligibilityTool()
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

        if is_cancellation_request(query):
            return self.cancellation_eligibility_tool.execute(order_number)

        return self.order_lookup_tool.execute(order_number)
