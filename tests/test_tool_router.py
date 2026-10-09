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


class FakeRefundStatusTool:
    name = "get_refund_status"

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
                "order_found": True,
                "refund_found": True,
                "status": "processing",
            },
        )


class FakeRefundEligibilityTool:
    name = "check_refund_eligibility"

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

    cancellation = FakeCancellationEligibilityTool()

    router = ToolRouter(
        order_lookup_tool=order_lookup,
        cancellation_eligibility_tool=(cancellation),
    )

    return (
        router,
        order_lookup,
        cancellation,
    )


def create_router_with_refund():
    order_lookup = FakeOrderLookupTool()

    cancellation = FakeCancellationEligibilityTool()

    refund = FakeRefundStatusTool()

    refund_eligibility = FakeRefundEligibilityTool()

    router = ToolRouter(
        order_lookup_tool=order_lookup,
        cancellation_eligibility_tool=cancellation,
        refund_status_tool=refund,
        refund_eligibility_tool=refund_eligibility,
    )

    return (
        router,
        order_lookup,
        cancellation,
        refund,
    )


def test_tracking_question_uses_order_lookup():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run("Where is order ORD-10001?")

    assert result is not None
    assert result.tool_name == "get_order"

    assert order_lookup.calls == ["ORD-10001"]

    assert cancellation.calls == []


def test_cancellation_question_uses_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run("Can I cancel ORD-10002?")

    assert result is not None

    assert result.tool_name == "check_cancellation_eligibility"

    assert cancellation.calls == ["ORD-10002"]

    assert order_lookup.calls == []


def test_cancel_order_wording_uses_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run("Cancel my order ORD-10002")

    assert result is not None

    assert result.tool_name == "check_cancellation_eligibility"

    assert cancellation.calls == ["ORD-10002"]

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
            content=("Where is order ORD-10002?"),
        ),
        ConversationTurn(
            role="assistant",
            content=("Your order is processing."),
        ),
    ]

    result = router.run(
        "Can I cancel it?",
        conversation_history=history,
    )

    assert result is not None

    assert result.tool_name == "check_cancellation_eligibility"

    assert cancellation.calls == ["ORD-10002"]

    assert order_lookup.calls == []


def test_order_number_is_normalized():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run("Where is ord-10001?")

    assert result is not None
    assert result.tool_name == "get_order"

    assert order_lookup.calls == ["ORD-10001"]

    assert cancellation.calls == []


def test_query_without_order_number_uses_no_tool():
    (
        router,
        order_lookup,
        cancellation,
    ) = create_router()

    result = router.run("How can I reset my password?")

    assert result is None

    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_question_uses_refund_status_tool():
    (
        router,
        order_lookup,
        cancellation,
        refund,
    ) = create_router_with_refund()

    result = router.run("Where is my refund for ORD-10003?")

    assert result is not None

    assert result.tool_name == "get_refund_status"

    assert refund.calls == ["ORD-10003"]

    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_followup_uses_order_from_history():
    (
        router,
        order_lookup,
        cancellation,
        refund,
    ) = create_router_with_refund()

    history = [
        ConversationTurn(
            role="user",
            content=("I was asking about ORD-10003."),
        ),
        ConversationTurn(
            role="assistant",
            content=("How can I help with that order?"),
        ),
    ]

    result = router.run(
        "Has my refund arrived?",
        conversation_history=history,
    )

    assert result is not None

    assert result.tool_name == "get_refund_status"

    assert refund.calls == ["ORD-10003"]

    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_order_number_is_normalized():
    (
        router,
        order_lookup,
        cancellation,
        refund,
    ) = create_router_with_refund()

    result = router.run("What is the refund status for ord-10003?")

    assert result is not None

    assert result.tool_name == "get_refund_status"

    assert refund.calls == ["ORD-10003"]

    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_about_cancelled_order_uses_refund_tool():
    (
        router,
        order_lookup,
        cancellation,
        refund,
    ) = create_router_with_refund()

    result = router.run("What is the refund status for cancelled order ORD-10002?")

    assert result is not None

    assert result.tool_name == "get_refund_status"

    assert refund.calls == ["ORD-10002"]

    assert cancellation.calls == []
    assert order_lookup.calls == []


def test_order_and_refund_status_request_uses_both_tools():
    (
        router,
        order_lookup,
        cancellation,
        refund,
    ) = create_router_with_refund()

    result = router.run("What is the order status and refund status for ORD-10003?")

    assert isinstance(result, list)
    assert len(result) == 2

    assert result[0].tool_name == "get_order"
    assert result[1].tool_name == "get_refund_status"

    assert order_lookup.calls == ["ORD-10003"]

    assert refund.calls == ["ORD-10003"]

    assert cancellation.calls == []


def test_refund_action_request_uses_refund_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
        refund_status,
    ) = create_router_with_refund()

    refund_eligibility = router.refund_eligibility_tool

    result = router.run("Refund ORD-10002")

    assert result is not None

    assert result.tool_name == ("check_refund_eligibility")

    assert refund_eligibility.calls == ["ORD-10002"]

    assert refund_status.calls == []
    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_eligibility_question_uses_refund_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
        refund_status,
    ) = create_router_with_refund()

    refund_eligibility = router.refund_eligibility_tool

    result = router.run("Can I get a refund for ORD-10002?")

    assert result is not None

    assert result.tool_name == ("check_refund_eligibility")

    assert refund_eligibility.calls == ["ORD-10002"]

    assert refund_status.calls == []
    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_action_followup_uses_order_from_history():
    (
        router,
        order_lookup,
        cancellation,
        refund_status,
    ) = create_router_with_refund()

    refund_eligibility = router.refund_eligibility_tool

    history = [
        ConversationTurn(
            role="user",
            content="I'm asking about ORD-10002.",
        ),
        ConversationTurn(
            role="assistant",
            content="How can I help with that order?",
        ),
    ]

    result = router.run(
        "Can I get a refund?",
        conversation_history=history,
    )

    assert result is not None

    assert result.tool_name == ("check_refund_eligibility")

    assert refund_eligibility.calls == ["ORD-10002"]

    assert refund_status.calls == []
    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_status_request_does_not_use_refund_eligibility_tool():
    (
        router,
        order_lookup,
        cancellation,
        refund_status,
    ) = create_router_with_refund()

    refund_eligibility = router.refund_eligibility_tool

    result = router.run("What is the refund status for ORD-10003?")

    assert result is not None

    assert result.tool_name == "get_refund_status"

    assert refund_status.calls == ["ORD-10003"]

    assert refund_eligibility.calls == []
    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_router_accepts_refund_eligibility_tool():
    order_lookup = FakeOrderLookupTool()
    cancellation = FakeCancellationEligibilityTool()
    refund_status = FakeRefundStatusTool()
    refund_eligibility = FakeRefundEligibilityTool()

    router = ToolRouter(
        order_lookup_tool=order_lookup,
        cancellation_eligibility_tool=cancellation,
        refund_status_tool=refund_status,
        refund_eligibility_tool=refund_eligibility,
    )

    result = router.run("Refund ORD-10002")

    assert result is not None

    assert result.tool_name == ("check_refund_eligibility")

    assert refund_eligibility.calls == ["ORD-10002"]

    assert refund_status.calls == []
    assert order_lookup.calls == []
    assert cancellation.calls == []


def test_refund_status_question_does_not_trigger_refund_eligibility():

    router, _, _, _ = create_router_with_refund()

    result = router.run("Can I get a refund status for ORD-10002?")

    assert result.tool_name == "get_refund_status"
