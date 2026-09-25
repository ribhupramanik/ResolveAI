import pytest

from src.rag.context_builder import RetrievedContext
from src.rag.prompt_builder import PromptBuilder, PromptPayload


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


def test_prompt_payload_is_generated(prompt_builder, sample_context):
    result = prompt_builder.build("my refund has not arrived", sample_context)

    assert isinstance(
        result,
        PromptPayload,
    )

    assert result.system_prompt
    assert result.user_prompt


def test_user_prompt_contains_query(prompt_builder, sample_context):
    query = "my refund has not arrived"

    result = prompt_builder.build(query, sample_context)

    assert query in result.user_prompt


def test_user_prompt_contains_context(prompt_builder, sample_context):
    result = prompt_builder.build("where is my refund", sample_context)

    assert sample_context.context in result.user_prompt


def test_system_prompt_contains_safety_rules(prompt_builder, sample_context):
    result = prompt_builder.build("where is my refund", sample_context)

    assert "Do not invent" in result.system_prompt

    assert "Do not claim that you performed an action" in result.system_prompt

    assert "Do not blindly copy historical responses" in result.system_prompt


def test_no_context_fallback(prompt_builder):
    empty_context = RetrievedContext(
        context="", retrieved_count=0, max_similarity=None, min_similarity=None
    )

    result = prompt_builder.build("I need help with my account", empty_context)

    assert (
        "No sufficiently relevant "
        "historical examples were retrieved." in result.user_prompt
    )


def test_empty_query_raises_error(
    prompt_builder,
    sample_context,
):

    with pytest.raises(ValueError):
        prompt_builder.build(
            "   ",
            sample_context,
        )


def test_non_string_query_raises_error(
    prompt_builder,
    sample_context,
):

    with pytest.raises(TypeError):
        prompt_builder.build(
            123,
            sample_context,
        )
