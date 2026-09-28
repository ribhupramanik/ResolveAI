import pytest

from src.rag.knowledge_retriever import (
    VerifiedKnowledgeContext,
)
from src.rag.response_validator import (
    ResponseValidator,
)
from src.rag.system_capabilities import (
    SystemCapabilitiesContext,
)


@pytest.fixture
def validator():
    return ResponseValidator()


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
            "Capability: live_operational_data_access\n"
            "Status: unavailable\n"
            "Content: ResolveAI has no live access "
            "to customer account, order, refund, "
            "payment, shipment, or transaction data."
        ),
        capability_count=1,
        capabilities=[
            "live_operational_data_access",
        ],
    )


def test_clean_response_passes(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = (
        "I'm sorry your refund has not arrived yet. "
        "ResolveAI cannot verify the current refund "
        "status because live refund-status information "
        "is unavailable."
    )

    result = validator.validate(
        response,
        "my refund has not arrived",
        verified_knowledge,
        system_capabilities,
    )

    assert result.is_valid
    assert result.issue_count == 0


def test_placeholder_is_detected(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = "Please visit {{Website URL}} for assistance."

    result = validator.validate(
        response,
        "I need help",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(issue.code == "unresolved_placeholder" for issue in result.issues)


def test_action_claim_is_detected(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = "Please provide your order number. I can look into the details for you."

    result = validator.validate(
        response,
        "my refund has not arrived",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_future_action_is_detected(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = "I'll follow up once I have more information."

    result = validator.validate(
        response,
        "where is my refund",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_unsupported_numeric_claim_is_detected(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = "Refunds normally arrive within 5-10 business days."

    result = validator.validate(
        response,
        "where is my refund",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_numeric_claim" for issue in result.issues)


def test_supported_numeric_claim_is_allowed(
    validator,
    system_capabilities,
):

    numeric_knowledge = VerifiedKnowledgeContext(
        context=(
            "Verified knowledge item 1\n"
            "Topic: refund_timeline\n"
            "Content: Refund processing may take "
            "7 business days."
        ),
        retrieved_count=1,
        topics=[
            "refund_timeline",
        ],
        max_similarity=0.90,
    )

    response = (
        "The available information states that processing may take 7 business days."
    )

    result = validator.validate(
        response,
        "where is my refund",
        numeric_knowledge,
        system_capabilities,
    )

    assert result.is_valid


def test_numeric_claim_from_customer_query_is_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = "You said that you have been waiting 7 business days."

    result = validator.validate(
        response,
        "I have been waiting 7 business days",
        verified_knowledge,
        system_capabilities,
    )

    assert result.is_valid


def test_empty_response_raises_error(
    validator,
    verified_knowledge,
    system_capabilities,
):

    with pytest.raises(ValueError):
        validator.validate(
            "   ",
            "where is my refund",
            verified_knowledge,
            system_capabilities,
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
        # Cases found during RAG evaluation
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
        ("I can forward that information to the team that handles refunds."),
        ("I can forward those details to the support team."),
        "I can pass along those details.",
        "I'll pass along that information.",
        ("We can pass this along to the appropriate team."),
        ("Let me know if you'd like me to pass along those details."),
    ],
)
def test_unsupported_action_claims_are_detected(
    validator,
    verified_knowledge,
    system_capabilities,
    response,
):

    result = validator.validate(
        response,
        "where is my refund",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


@pytest.mark.parametrize(
    "response",
    [
        (
            "You may want to contact the support team "
            "that handled your original purchase."
        ),
        (
            "Please reach out to customer support "
            "for more information."
        ),
        (
            "You can visit the help center "
            "for assistance."
        ),
    ],
)
def test_unsupported_support_routes_are_detected(
    validator,
    verified_knowledge,
    system_capabilities,
    response,
):

    result = validator.validate(
        response,
        "where is my refund",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unsupported_support_route_claim"
        for issue in result.issues
    )


@pytest.mark.parametrize(
    "response",
    [
        (
            "You may want to contact your bank "
            "for more information."
        ),
        (
            "Please contact the merchant "
            "about the refund."
        ),
        (
            "You may want to reach out directly "
            "to the merchant for more information."
        ),
        (
            "You can check with your bank "
            "about the transaction."
        ),
        (
            "You may want to check with the party "
            "that processed the refund directly."
        ),
    ],
)
def test_unsupported_third_party_claims_are_detected(
    validator,
    verified_knowledge,
    system_capabilities,
    response,
):

    result = validator.validate(
        response,
        "where is my refund",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(
        issue.code
        == "unsupported_third_party_claim"
        for issue in result.issues
    )