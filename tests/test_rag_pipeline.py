import pytest

from src.rag.context_builder import (
    RetrievedContext,
)
from src.rag.generator import (
    GeneratedResponse,
)
from src.rag.knowledge_retriever import (
    VerifiedKnowledgeContext,
)
from src.rag.pipeline import (
    SAFE_FALLBACK,
    ResolveAIPipeline,
)
from src.rag.prompt_builder import (
    PromptPayload,
)
from src.rag.response_validator import (
    ResponseValidator,
)

from src.rag.system_capabilities import (
    SystemCapabilitiesContext,
)


class FakeContextBuilder:
    def build(
        self,
        query,
    ):

        return RetrievedContext(
            context=(
                "Example 1\n"
                "Customer request: "
                "where is my refund\n"
                "Historical resolution: "
                "Please provide your order "
                "number and refund request date.\n"
                "Intent: track_refund\n"
                "Similarity: 0.8200"
            ),
            retrieved_count=1,
            max_similarity=0.82,
            min_similarity=0.82,
        )


class FakeKnowledgeRetriever:
    def build(
        self,
        query,
    ):

        return VerifiedKnowledgeContext(
            context=(
                "Verified knowledge item 1\n"
                "Topic: refund_status\n"
                "Content: No live refund-status "
                "integration is currently available."
            ),
            retrieved_count=1,
            topics=[
                "refund_status",
            ],
            max_similarity=0.90,
        )

class FakeSystemCapabilitiesProvider:

    def build(
        self,
    ):

        return SystemCapabilitiesContext(
            context=(
                "System capability 1\n"
                "Capability: human_support_routing\n"
                "Status: unavailable\n"
                "Content: ResolveAI cannot "
                "transfer or connect customers "
                "to a human support agent."
            ),
            capability_count=1,
            capabilities=[
                "human_support_routing",
            ],
        )


class FakePromptBuilder:
    def build(
        self,
        query,
        retrieved_context,
        verified_knowledge,
        system_capabilities,
    ):

        return PromptPayload(
            system_prompt=("Follow the support rules."),
            user_prompt=(f"Customer request: {query}"),
        )


class SequenceGenerator:
    def __init__(
        self,
        responses,
    ):

        self.responses = responses
        self.call_count = 0

    def generate(
        self,
        prompt,
    ):

        response = self.responses[self.call_count]

        self.call_count += 1

        return GeneratedResponse(
            text=response,
            model="fake-model",
            provider="fake",
        )


def create_pipeline(
    responses,
):

    return ResolveAIPipeline(
        generator=SequenceGenerator(responses),
        context_builder=FakeContextBuilder(),
        knowledge_retriever=FakeKnowledgeRetriever(),
        system_capabilities_provider= FakeSystemCapabilitiesProvider(),
        prompt_builder=FakePromptBuilder(),
        validator=ResponseValidator(),
    )


def test_valid_first_response():

    pipeline = create_pipeline(
        [("Please provide your order number and refund request date.")]
    )

    result = pipeline.run("my refund has not arrived")

    assert result.attempts == 1
    assert not result.used_fallback
    assert result.validation_issues == []
    assert result.verified_knowledge_count == 1

    assert result.verified_knowledge_topics == ["refund_status"]

    assert (result.system_capability_count == 1)

    assert ( result.system_capabilities == ["human_support_routing"])

    assert "order number" in result.text


def test_invalid_first_response_is_retried():

    pipeline = create_pipeline(
        [
            ("I can look into your refund for you."),
            ("Please provide your order number and refund request date."),
        ]
    )

    result = pipeline.run("my refund has not arrived")

    assert result.attempts == 2
    assert not result.used_fallback

    assert len(result.validation_issues) > 0

    assert any(
        issue.code == "unsupported_action_claim" for issue in result.validation_issues
    )


def test_two_invalid_responses_use_fallback():

    pipeline = create_pipeline(
        [
            ("I can look into your refund for you."),
            ("I'll investigate this for you."),
        ]
    )

    result = pipeline.run("my refund has not arrived")

    assert result.attempts == 2
    assert result.used_fallback

    assert result.text == SAFE_FALLBACK

    assert len(result.validation_issues) >= 2


def test_empty_query_raises_error():

    pipeline = create_pipeline(["Valid response."])

    with pytest.raises(ValueError):
        pipeline.run("   ")


def test_non_string_query_raises_error():

    pipeline = create_pipeline(["Valid response."])

    with pytest.raises(TypeError):
        pipeline.run(123)
