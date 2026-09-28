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

    response = "Please visit {{Website URL}} for assistance."

    result = validator.validate(
        response,
        "I need help",
        context,
    )

    assert not result.is_valid

    assert any(issue.code == "unresolved_placeholder" for issue in result.issues)


def test_action_claim_is_detected(
    validator,
    context,
):

    response = "Please provide your order number. I can look into the details for you."

    result = validator.validate(
        response,
        "my refund has not arrived",
        context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_future_action_is_detected(
    validator,
    context,
):

    response = "I'll follow up once I have more information."

    result = validator.validate(
        response,
        "where is my refund",
        context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_unsupported_numeric_claim_is_detected(
    validator,
    context,
):

    response = "Refunds normally arrive within 5-10 business days."

    result = validator.validate(
        response,
        "where is my refund",
        context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_numeric_claim" for issue in result.issues)


def test_supported_numeric_claim_is_allowed(
    validator,
):

    context = RetrievedContext(
        context=("Historical resolution: Refund processing may take 7 business days."),
        retrieved_count=1,
        max_similarity=0.80,
        min_similarity=0.80,
    )

    response = (
        "The available information states that processing may take 7 business days."
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

    with pytest.raises(ValueError):
        validator.validate(
            "   ",
            "where is my refund",
            context,
        )


@pytest.mark.parametrize(
    "response",
    [
        # Existing cases
        "I'll follow up once I have more information.",
        "We'll investigate this for you.",
        "I'll check the status for you.",
        "I've checked your account.",
        "We can look into this for you.",
        "I can help you check the status.",
        "I'll be able to look into the situation for you.",
        "We can help you investigate the issue.",
        "I've forwarded your request to our team.",
        "I can look up the current order status.",
        "I'll look up the delivery estimate.",
        "I can connect you to a human agent.",
        "We'll transfer you to support.",
        "I can provide you with the latest status.",
        # New cases found during RAG evaluation
        "I'll forward your request to our support team.",
        "I will forward your request to the appropriate team.",
        "We'll forward this to customer support.",
        "We will send your request to the relevant department.",
        "I'll send this to our support team.",
        "I can provide you with the current order status.",
        "I can provide you with the latest refund status.",
        "I can give you an accurate delivery estimate.",
        "I can give you the current status of your shipment.",
        "I can help you get connected to a human agent.",
        "I can help you connect with customer support.",
        "I can help you locate the status of your refund.",
        "I can help you locate your order.",
        "I'll route your request to the appropriate team.",
        "We can route this to customer support.",
        "I can forward that information to the team that handles refunds.",
        "I can forward those details to the support team.",
        "I can pass along those details.",
        "I'll pass along that information.",
        "We can pass this along to the appropriate team.",
        "Let me know if you'd like me to pass along those details.",
    ],
)
def test_unsupported_action_claims_are_detected(
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

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)
