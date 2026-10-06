from src.rag.context_builder import RetrievedContext
from src.rag.generator import GeneratedResponse
from src.rag.knowledge_retriever import (
    VerifiedKnowledgeContext,
)
from src.rag.pipeline import ResolveAIPipeline
from src.rag.prompt_builder import PromptPayload
from src.rag.response_validator import ResponseValidator
from src.rag.system_capabilities import (
    SystemCapabilitiesContext,
)
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
                "status": "delivered",
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
                "refund_number": "REF-10003",
                "status": "processing",
                "amount": "3899.00",
                "currency": "INR",
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

        raise AssertionError(
            "Cancellation tool should not be called."
        )


class FakeContextBuilder:
    def build(
        self,
        query: str,
    ) -> RetrievedContext:
        return RetrievedContext(
            context="No historical examples required.",
            retrieved_count=0,
            max_similarity=0.0,
            min_similarity=0.0,
        )


class FakeKnowledgeRetriever:
    def build(
        self,
        query: str,
    ) -> VerifiedKnowledgeContext:
        return VerifiedKnowledgeContext(
            context="No additional verified knowledge.",
            retrieved_count=0,
            topics=[],
            max_similarity=0.0,
        )


class FakeSystemCapabilitiesProvider:
    def build(
        self,
    ) -> SystemCapabilitiesContext:
        return SystemCapabilitiesContext(
            context="No additional capability context.",
            capability_count=0,
            capabilities=[],
        )


class CapturingPromptBuilder:
    def __init__(self):
        self.last_operational_context = None

    def build(
        self,
        query,
        retrieved_context,
        verified_knowledge,
        system_capabilities,
        conversation_history=None,
        operational_context=None,
    ) -> PromptPayload:
        self.last_operational_context = (
            operational_context
        )

        return PromptPayload(
            system_prompt=(
                "Use authoritative operational evidence."
            ),
            user_prompt=query,
        )


class FakeGenerator:
    def __init__(self):
        self.call_count = 0

    def generate(
        self,
        prompt,
    ) -> GeneratedResponse:
        self.call_count += 1

        return GeneratedResponse(
            text=(
                "I've checked the order and refund "
                "status. ORD-10003 is delivered and "
                "its ₹3899.00 refund is processing."
            ),
            provider="fake",
            model="fake-model",
        )


def test_order_and_refund_multi_tool_pipeline_integration():
    order_lookup = FakeOrderLookupTool()
    refund_status = FakeRefundStatusTool()

    cancellation = (
        FakeCancellationEligibilityTool()
    )

    router = ToolRouter(
        order_lookup_tool=order_lookup,
        cancellation_eligibility_tool=(
            cancellation
        ),
        refund_status_tool=refund_status,
    )

    prompt_builder = CapturingPromptBuilder()
    generator = FakeGenerator()

    pipeline = ResolveAIPipeline(
        generator=generator,
        context_builder=FakeContextBuilder(),
        knowledge_retriever=(
            FakeKnowledgeRetriever()
        ),
        system_capabilities_provider=(
            FakeSystemCapabilitiesProvider()
        ),
        prompt_builder=prompt_builder,
        validator=ResponseValidator(),
        tool_router=router,
    )

    result = pipeline.run(
        (
            "What is the order status and "
            "refund status for ORD-10003?"
        )
    )

    # Both operational tools were actually called.
    assert order_lookup.calls == [
        "ORD-10003"
    ]

    assert refund_status.calls == [
        "ORD-10003"
    ]

    assert cancellation.calls == []

    # The generator only needed one attempt.
    assert generator.call_count == 1
    assert result.attempts == 1
    assert result.used_fallback is False

    # Multi-tool legacy metadata remains deliberately
    # singular/empty.
    assert result.tool_used is True
    assert result.tool_name is None
    assert result.tool_success is None
    assert result.tool_data is None

    # Structured tool evidence is preserved.
    assert len(result.tool_results) == 2

    assert (
        result.tool_results[0].tool_name
        == "get_order"
    )

    assert (
        result.tool_results[1].tool_name
        == "get_refund_status"
    )

    assert all(
        tool_result.success
        for tool_result in result.tool_results
    )

    # Combined operational evidence reached
    # the prompt layer.
    operational_context = (
        prompt_builder.last_operational_context
    )

    assert operational_context is not None

    assert len(
        operational_context.tool_results
    ) == 2

    assert (
        "Tool: get_order"
        in operational_context.context
    )

    assert (
        "Tool: get_refund_status"
        in operational_context.context
    )

    assert (
        "amount: 3899.00"
        in operational_context.context
    )

    # The real validator accepted the combined,
    # operationally-grounded answer.
    assert result.validation_issues == []

    assert (
        result.text
        == (
            "I've checked the order and refund "
            "status. ORD-10003 is delivered and "
            "its ₹3899.00 refund is processing."
        )
    )