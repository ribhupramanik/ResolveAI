import pytest

from src.rag.context_builder import (
    RetrievedContext,
)

from src.rag.response_validator import (
    ResponseValidator,
)


@pytest.fixture
def validator():
    return ResponseValidator()


@pytest.fixture
def context():

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


def test_clean_response_passes(
    validator,
    context,
):

    response = (
        "I'm sorry your refund has not "
        "arrived yet. Please provide your "
        "order number and the date you "
        "requested the refund."
    )

    result = validator.validate(
        response,
        "my refund has not arrived",
        context,
    )

    assert result.is_valid
    assert result.issue_count == 0


def test_placeholder_is_detected(
    validator,
    context,
):

    response = (
        "Please visit {{Website URL}} "
        "for assistance."
    )

    result = validator.validate(
        response,
        "I need help",
        context,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unresolved_placeholder"
        for issue in result.issues
    )


def test_action_claim_is_detected(
    validator,
    context,
):

    response = (
        "Please provide your order number. "
        "I can look into the details for you."
    )

    result = validator.validate(
        response,
        "my refund has not arrived",
        context,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unsupported_action_claim"
        for issue in result.issues
    )


def test_future_action_is_detected(
    validator,
    context,
):

    response = (
        "I'll follow up once I have "
        "more information."
    )

    result = validator.validate(
        response,
        "where is my refund",
        context,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unsupported_action_claim"
        for issue in result.issues
    )


def test_unsupported_numeric_claim_is_detected(
    validator,
    context,
):

    response = (
        "Refunds normally arrive within "
        "5-10 business days."
    )

    result = validator.validate(
        response,
        "where is my refund",
        context,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unsupported_numeric_claim"
        for issue in result.issues
    )


def test_supported_numeric_claim_is_allowed(
    validator,
):

    context = RetrievedContext(
        context=(
            "Historical resolution: "
            "Refund processing may take "
            "7 business days."
        ),
        retrieved_count=1,
        max_similarity=0.80,
        min_similarity=0.80,
    )

    response = (
        "The available information states "
        "that processing may take "
        "7 business days."
    )

    result = validator.validate(
        response,
        "where is my refund",
        context,
    )

    assert result.is_valid


def test_empty_response_raises_error(
    validator,
    context,
):

    with pytest.raises(
        ValueError
    ):
        validator.validate(
            "   ",
            "where is my refund",
            context,
        )

@pytest.mark.parametrize(
    "response",
    [
        "I'll follow up once I have more information.",
        "We'll investigate this for you.",
        "I'll check the status for you.",
        "I've checked your account.",
        "We can look into this for you.",
    ],
)
def test_action_contractions_are_detected(
    validator,
    context,
    response,
):

    result = validator.validate(
        response,
        "where is my refund",
        context,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unsupported_action_claim"
        for issue in result.issues
    )