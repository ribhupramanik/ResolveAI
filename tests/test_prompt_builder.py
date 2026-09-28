import pytest

from src.rag.context_builder import (
    RetrievedContext,
)
from src.rag.knowledge_retriever import (
    VerifiedKnowledgeContext,
)
from src.rag.prompt_builder import (
    PromptBuilder,
    PromptPayload,
)
from src.rag.system_capabilities import (
    SystemCapabilitiesContext,
)


@pytest.fixture
def prompt_builder():
    return PromptBuilder()


@pytest.fixture
def sample_context():

    return RetrievedContext(
        context=(
            "Example 1\n"
            "Customer request: where is my refund\n"
            "Historical resolution: Please provide "
            "your refund details.\n"
            "Intent: track_refund\n"
            "Similarity: 0.8200"
        ),
        retrieved_count=1,
        max_similarity=0.82,
        min_similarity=0.82,
    )


@pytest.fixture
def verified_knowledge():

    return VerifiedKnowledgeContext(
        context=(
            "Verified knowledge item 1\n"
            "Topic: refund_status\n"
            "Content: No live refund-status "
            "integration is currently available. "
            "ResolveAI cannot verify the current "
            "status of a customer's refund."
        ),
        retrieved_count=1,
        topics=[
            "refund_status",
        ],
        max_similarity=0.90,
    )


@pytest.fixture
def system_capabilities():

    return SystemCapabilitiesContext(
        context=(
            "System capability 1\n"
            "Capability: human_support_routing\n"
            "Status: unavailable\n"
            "Content: ResolveAI cannot currently "
            "transfer, connect, route, forward, or "
            "escalate a conversation to a human "
            "support agent."
        ),
        capability_count=1,
        capabilities=[
            "human_support_routing",
        ],
    )


def test_prompt_payload_is_generated(
    prompt_builder,
    sample_context,
    verified_knowledge,
    system_capabilities,
):

    result = prompt_builder.build(
        "my refund has not arrived",
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert isinstance(
        result,
        PromptPayload,
    )

    assert result.system_prompt
    assert result.user_prompt


def test_user_prompt_contains_query(
    prompt_builder,
    sample_context,
    verified_knowledge,
    system_capabilities,
):

    query = "my refund has not arrived"

    result = prompt_builder.build(
        query,
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert query in result.user_prompt


def test_user_prompt_contains_historical_context(
    prompt_builder, sample_context, verified_knowledge, system_capabilities
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert sample_context.context in result.user_prompt


def test_user_prompt_contains_verified_knowledge(
    prompt_builder, sample_context, verified_knowledge, system_capabilities
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert "VERIFIED KNOWLEDGE:" in result.user_prompt

    assert verified_knowledge.context in result.user_prompt

    assert "refund_status" in result.user_prompt


def test_system_prompt_contains_safety_rules(
    prompt_builder, sample_context, verified_knowledge, system_capabilities
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert "Never invent or assume" in result.system_prompt

    assert "Never claim that ResolveAI checked" in result.system_prompt

    assert "Do not blindly copy historical responses" in result.system_prompt

    assert "VERIFIED KNOWLEDGE" in result.system_prompt


def test_no_historical_context_fallback(
    prompt_builder, verified_knowledge, system_capabilities
):

    empty_context = RetrievedContext(
        context="",
        retrieved_count=0,
        max_similarity=None,
        min_similarity=None,
    )

    result = prompt_builder.build(
        "I need help with my account",
        empty_context,
        verified_knowledge,
        system_capabilities,
    )

    assert (
        "No sufficiently relevant historical "
        "examples were retrieved." in result.user_prompt
    )


def test_no_verified_knowledge_fallback(
    prompt_builder, sample_context, system_capabilities
):

    empty_knowledge = VerifiedKnowledgeContext(
        context="",
        retrieved_count=0,
        topics=[],
        max_similarity=None,
    )

    result = prompt_builder.build(
        "I need help with my account",
        sample_context,
        empty_knowledge,
        system_capabilities,
    )

    assert "No relevant verified knowledge was retrieved." in result.user_prompt


def test_context_sections_are_separate(
    prompt_builder, sample_context, verified_knowledge, system_capabilities
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert "RETRIEVED HISTORICAL EXAMPLES:" in result.user_prompt

    assert "VERIFIED KNOWLEDGE:" in result.user_prompt

    assert (
        result.user_prompt.index("RETRIEVED HISTORICAL EXAMPLES:")
        < result.user_prompt.index("VERIFIED KNOWLEDGE:")
        < result.user_prompt.index("SYSTEM CAPABILITIES:")
    )


def test_empty_query_raises_error(
    prompt_builder,
    sample_context,
    verified_knowledge,
    system_capabilities,
):

    with pytest.raises(ValueError):
        prompt_builder.build(
            "   ", sample_context, verified_knowledge, system_capabilities
        )


def test_non_string_query_raises_error(
    prompt_builder, sample_context, verified_knowledge, system_capabilities
):

    with pytest.raises(TypeError):
        prompt_builder.build(
            123, sample_context, verified_knowledge, system_capabilities
        )


def test_user_prompt_contains_system_capabilities(
    prompt_builder,
    sample_context,
    verified_knowledge,
    system_capabilities,
):

    result = prompt_builder.build(
        "I need to speak with a human",
        sample_context,
        verified_knowledge,
        system_capabilities,
    )

    assert "SYSTEM CAPABILITIES:" in result.user_prompt

    assert system_capabilities.context in result.user_prompt

    assert "human_support_routing" in result.user_prompt

def test_no_system_capabilities_fallback(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    empty_capabilities = SystemCapabilitiesContext(
        context="",
        capability_count=0,
        capabilities=[],
    )

    result = prompt_builder.build(
        "I need help",
        sample_context,
        verified_knowledge,
        empty_capabilities,
    )

    assert (
        "No system capability information is available."
        in result.user_prompt
    )