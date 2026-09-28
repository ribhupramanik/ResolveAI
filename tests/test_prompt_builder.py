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


def test_prompt_payload_is_generated(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    result = prompt_builder.build(
        "my refund has not arrived",
        sample_context,
        verified_knowledge,
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
):

    query = "my refund has not arrived"

    result = prompt_builder.build(
        query,
        sample_context,
        verified_knowledge,
    )

    assert query in result.user_prompt


def test_user_prompt_contains_historical_context(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
    )

    assert sample_context.context in result.user_prompt


def test_user_prompt_contains_verified_knowledge(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
    )

    assert "VERIFIED KNOWLEDGE:" in result.user_prompt

    assert verified_knowledge.context in result.user_prompt

    assert "refund_status" in result.user_prompt


def test_system_prompt_contains_safety_rules(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
    )

    assert "Never invent or assume" in result.system_prompt

    assert "Never claim that ResolveAI checked" in result.system_prompt

    assert "Do not blindly copy historical responses" in result.system_prompt

    assert "VERIFIED KNOWLEDGE" in result.system_prompt


def test_no_historical_context_fallback(
    prompt_builder,
    verified_knowledge,
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
    )

    assert (
        "No sufficiently relevant historical "
        "examples were retrieved." in result.user_prompt
    )


def test_no_verified_knowledge_fallback(
    prompt_builder,
    sample_context,
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
    )

    assert "No relevant verified knowledge was retrieved." in result.user_prompt


def test_historical_and_verified_context_are_separate(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    result = prompt_builder.build(
        "where is my refund",
        sample_context,
        verified_knowledge,
    )

    assert "RETRIEVED HISTORICAL EXAMPLES:" in result.user_prompt

    assert "VERIFIED KNOWLEDGE:" in result.user_prompt

    assert result.user_prompt.index(
        "RETRIEVED HISTORICAL EXAMPLES:"
    ) < result.user_prompt.index("VERIFIED KNOWLEDGE:")


def test_empty_query_raises_error(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    with pytest.raises(ValueError):
        prompt_builder.build(
            "   ",
            sample_context,
            verified_knowledge,
        )


def test_non_string_query_raises_error(
    prompt_builder,
    sample_context,
    verified_knowledge,
):

    with pytest.raises(TypeError):
        prompt_builder.build(
            123,
            sample_context,
            verified_knowledge,
        )
