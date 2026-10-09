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
from src.tools.refund_status_tool import (
    RefundStatusTool,
)

from src.tools.refund_eligibility_tool import (
    RefundEligibilityTool,
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

REFUND_REQUEST_PATTERN = re.compile(
    r"\brefund(?:s|ed|ing)?\b",
    re.IGNORECASE,
)

ORDER_STATUS_PATTERN = re.compile(
    r"\border\s+status\b",
    re.IGNORECASE,
)

REFUND_ACTION_PATTERN = re.compile(
    r"^\s*refund\s+"
    r"(?:(?:my|the|this)\s+)?"
    r"(?:order\s+)?"
    r"ORD-\d+\b",
    re.IGNORECASE,
)

REFUND_ELIGIBILITY_QUESTION_PATTERN = re.compile(
    r"\bcan\s+i\s+"
    r"(?:get|receive)\s+"
    r"(?:a\s+)?refund\b"
    r"(?!\s+status\b)",
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


def is_cancellation_request(
    query: str,
) -> bool:

    return any(pattern.search(query) for pattern in CANCELLATION_REQUEST_PATTERNS)


def is_refund_request(
    query: str,
) -> bool:

    return REFUND_REQUEST_PATTERN.search(query) is not None


def is_refund_action_request(
    query: str,
) -> bool:

    return (
        REFUND_ACTION_PATTERN.search(query) is not None
        or REFUND_ELIGIBILITY_QUESTION_PATTERN.search(query) is not None
    )


def is_order_status_request(
    query: str,
) -> bool:

    return ORDER_STATUS_PATTERN.search(query) is not None


class ToolRouter:
    def __init__(
        self,
        order_lookup_tool: OrderLookupTool | None = None,
        cancellation_eligibility_tool:
            CancellationEligibilityTool | None = None,
        refund_status_tool:
            RefundStatusTool | None = None,
        refund_eligibility_tool:
            RefundEligibilityTool | None = None,
    ):
        self.order_lookup_tool = (
            order_lookup_tool
            if order_lookup_tool is not None
            else OrderLookupTool()
        )

        self.cancellation_eligibility_tool = (
            cancellation_eligibility_tool
            if cancellation_eligibility_tool is not None
            else CancellationEligibilityTool()
        )

        self.refund_status_tool = (
            refund_status_tool
            if refund_status_tool is not None
            else RefundStatusTool()
        )

        self.refund_eligibility_tool = (
            refund_eligibility_tool
            if refund_eligibility_tool is not None
            else RefundEligibilityTool()
        )

    def run(
        self,
        query: str,
        conversation_history: list[ConversationTurn] | None = None,
    ) -> ToolResult | list[ToolResult] | None:

        order_number = extract_order_number(
            query,
            conversation_history,
        )

        if order_number is None:
            return None

        if is_refund_request(query) and is_order_status_request(query):
            return [
                self.order_lookup_tool.execute(order_number),
                self.refund_status_tool.execute(order_number),
            ]

        if is_refund_action_request(query):
            return self.refund_eligibility_tool.execute(order_number)

        if is_refund_request(query):
            return self.refund_status_tool.execute(order_number)

        if is_cancellation_request(query):
            return self.cancellation_eligibility_tool.execute(order_number)

        return self.order_lookup_tool.execute(order_number)
