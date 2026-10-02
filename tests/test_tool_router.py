from src.rag.conversation import ConversationTurn
from src.tools.base import ToolResult
from src.tools.router import ToolRouter


class FakeOrderLookupTool:
    name = "get_order"

    def __init__(self):
        self.calls = []

    def execute(
        self,
        order_number: str,
    ) -> ToolResult:
        self.calls.append(order_number)

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "order_number": order_number,
                "status": "shipped",
            },
        )


class FakeCancellationEligibilityTool:
    name = "check_cancellation_eligibility"

    def __init__(self):
        self.calls = []

    def execute(
        self,
        order_number: str,
    ) -> ToolResult:
        self.calls.append(order_number)

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "order_number": order_number,
                "eligible": True,
                "requires_confirmation": True,
                "action_performed": False,
            },
        )


def create_router():
    order_lookup = FakeOrderLookupTool()

    cancellation = (
        FakeCancellationEligibilityTool()
    )

    router = ToolRouter(
        order_lookup_tool=order_lookup,
        cancellation_eligibility_tool=(
            cancellation
        ),
    )

    return (
        router,
        order_lookup,
        cancellation,
    )


def test_tracking_question_uses_order_lookup():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run(
        "Where is order ORD-10001?"
    )

    assert result is not None
    assert result.tool_name == "get_order"

    assert order_lookup.calls == [
        "ORD-10001"
    ]

    assert cancellation.calls == []


def test_cancellation_question_uses_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run(
        "Can I cancel ORD-10002?"
    )

    assert result is not None

    assert (
        result.tool_name
        == "check_cancellation_eligibility"
    )

    assert cancellation.calls == [
        "ORD-10002"
    ]

    assert order_lookup.calls == []


def test_cancel_order_wording_uses_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run(
        "Cancel my order ORD-10002"
    )

    assert result is not None

    assert (
        result.tool_name
        == "check_cancellation_eligibility"
    )

    assert cancellation.calls == [
        "ORD-10002"
    ]

    assert order_lookup.calls == []


def test_cancellation_followup_uses_order_from_history():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    history = [
        ConversationTurn(
            role="user",
            content=(
                "Where is order ORD-10002?"
            ),
        ),
        ConversationTurn(
            role="assistant",
            content=(
                "Your order is processing."
            ),
        ),
    ]

    result = router.run(
        "Can I cancel it?",
        conversation_history=history,
    )

    assert result is not None

    assert (
        result.tool_name
        == "check_cancellation_eligibility"
    )

    assert cancellation.calls == [
        "ORD-10002"
    ]

    assert order_lookup.calls == []


def test_order_number_is_normalized():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run(
        "Where is ord-10001?"
    )

    assert result is not None
    assert result.tool_name == "get_order"

    assert order_lookup.calls == [
        "ORD-10001"
    ]

    assert cancellation.calls == []


def test_query_without_order_number_uses_no_tool():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run(
        "How can I reset my password?"
    )

    assert result is None

    assert order_lookup.calls == []
    assert cancellation.calls == []