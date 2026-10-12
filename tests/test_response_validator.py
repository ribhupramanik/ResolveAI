import pytest

from src.rag.knowledge_retriever import (
    VerifiedKnowledgeContext,
)
from src.rag.operational_context import (
    OperationalContext,
    build_operational_context,
)
from src.rag.response_validator import (
    ResponseValidator,
)
from src.rag.system_capabilities import (
    SystemCapabilitiesContext,
)
from src.tools.base import ToolResult


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
        ("Please reach out to customer support for more information."),
        ("You can visit the help center for assistance."),
        ("Please contact the relevant support channel."),
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
        issue.code == "unsupported_support_route_claim" for issue in result.issues
    )


@pytest.mark.parametrize(
    "response",
    [
        ("You may want to contact your bank for more information."),
        ("Please contact the merchant about the refund."),
        ("You may want to reach out directly to the merchant for more information."),
        ("You can check with your bank about the transaction."),
        ("You may want to check with the party that processed the refund directly."),
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

    assert any(issue.code == "unsupported_third_party_claim" for issue in result.issues)


@pytest.mark.parametrize(
    "response",
    [
        ("Please contact the company's customer support directly."),
        ("You may want to contact their customer support directly."),
        ("You may want to check the company's official website."),
        ("You may want to check any official help resources."),
        ("Try contacting the company through their official website."),
        ("Please use their customer-support phone number."),
        ("Contact their customer support through their official channels."),
        (
            "You may want to check any available "
            "customer support resources that the "
            "company provides."
        ),
        (
            "You may want to check any official "
            "resources or contact the company directly "
            "through their official channels."
        ),
        (
            "You can check any official communication "
            "or look for a link in your account portal."
        ),
        (
            "Please contact the company's "
            "customer-support team directly through "
            "their official website or "
            "customer-support phone number."
        ),
    ],
)
def test_unverified_support_routes_from_rag_eval_are_detected(
    validator,
    verified_knowledge,
    system_capabilities,
    response,
):
    result = validator.validate(
        response,
        "I need help",
        verified_knowledge,
        system_capabilities,
    )

    assert not result.is_valid

    assert any(
        issue.code == "unsupported_support_route_claim" for issue in result.issues
    )


def test_negative_support_route_statement_is_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):

    response = "No verified customer-support route is currently available."

    result = validator.validate(
        response,
        "I need help",
        verified_knowledge,
        system_capabilities,
    )

    assert result.is_valid


def test_numeric_claim_from_successful_operational_data_is_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- total_amount: 2499.00\n"
            "- currency: INR\n"
            "- estimated_delivery: 2026-10-04"
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=True,
    )

    result = validator.validate(
        response_text="The order total is ₹2499.00.",
        query="Where is my order?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_wrong_currency_from_operational_data_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- total_amount: 2499.00\n"
            "- currency: INR"
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=True,
    )

    result = validator.validate(
        response_text=("The order total is $2499.00."),
        query="What is my order total?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_numeric_claim" for issue in result.issues)


def test_wrong_amount_from_operational_data_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- total_amount: 2499.00\n"
            "- currency: INR"
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=True,
    )

    result = validator.validate(
        response_text=("The order total is ₹3999.00."),
        query="What is my order total?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_numeric_claim" for issue in result.issues)


def test_numeric_claim_from_failed_operational_data_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: failed\n"
            "Data: {'order_number': 'ORD-10001'}\n"
            "Error: Order lookup failed."
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=False,
    )

    result = validator.validate(
        response_text="The order total is ₹2499.00.",
        query="Where is my order?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_numeric_claim" for issue in result.issues)


def test_unverified_tracking_website_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10001\n"
            "- carrier: DemoShip\n"
            "- tracking_number: DSH10001001"
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=True,
    )

    result = validator.validate(
        response_text=(
            "You can use the tracking number with "
            "DemoShip's website or app to see the "
            "current location of your shipment."
        ),
        query="Where is order ORD-10001?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_third_party_claim" for issue in result.issues)


def test_grounded_tracking_details_are_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- carrier: DemoShip\n"
            "- tracking_number: DSH10001001"
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=True,
    )

    result = validator.validate(
        response_text=(
            "The carrier is DemoShip and the tracking number is DSH10001001."
        ),
        query="Where is order ORD-10001?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_successful_order_lookup_allows_looked_up_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10001\n"
            "- status: shipped"
        ),
        tool_used=True,
        tool_name="get_order",
        tool_success=True,
    )

    result = validator.validate(
        response_text=("I've looked up your order. It is currently shipped."),
        query="Where is ORD-10001?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_failed_order_lookup_rejects_looked_up_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=("Tool: get_order\nTool status: failed\nError: Order not found."),
        tool_used=True,
        tool_name="get_order",
        tool_success=False,
    )

    result = validator.validate(
        response_text="I've looked up your order.",
        query="Where is ORD-99999?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_looked_up_claim_without_tool_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
):
    result = validator.validate(
        response_text="I've looked up your order.",
        query="Where is my order?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_successful_eligibility_check_allows_checked_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: check_cancellation_eligibility\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10002\n"
            "- eligible: True"
        ),
        tool_used=True,
        tool_name="check_cancellation_eligibility",
        tool_success=True,
    )

    result = validator.validate(
        response_text=(
            "I've checked the cancellation eligibility. "
            "ORD-10002 is eligible for cancellation."
        ),
        query="Can I cancel ORD-10002?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_failed_eligibility_check_rejects_checked_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: check_cancellation_eligibility\n"
            "Tool status: failed\n"
            "Error: Order not found."
        ),
        tool_used=True,
        tool_name="check_cancellation_eligibility",
        tool_success=False,
    )

    result = validator.validate(
        response_text=("I've checked the cancellation eligibility."),
        query="Can I cancel ORD-99999?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


@pytest.mark.parametrize(
    "response",
    [
        ("Please confirm the request through the channel you used to place the order."),
        ("You can use your account portal to cancel the order."),
        ("Use the order-management features on our platform."),
        ("Log into your account and select the cancellation option."),
        ("Check your order confirmation email for cancellation instructions."),
        (
            "You would need to use the cancellation process "
            "available through your account."
        ),
    ],
)
def test_unverified_cancellation_procedure_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
    response,
):
    result = validator.validate(
        response_text=response,
        query="Can I cancel ORD-10002?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
    )

    assert not result.is_valid

    assert any(
        issue.code == "unsupported_cancellation_procedure_claim"
        for issue in result.issues
    )


def test_grounded_cancellation_eligibility_response_is_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: check_cancellation_eligibility\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10002\n"
            "- status: processing\n"
            "- eligible: True\n"
            "- requires_confirmation: True\n"
            "- action_performed: False"
        ),
        tool_used=True,
        tool_name=("check_cancellation_eligibility"),
        tool_success=True,
    )

    result = validator.validate(
        response_text=(
            "ORD-10002 is eligible for cancellation "
            "because it is still processing. "
            "No cancellation has been performed."
        ),
        query="Can I cancel ORD-10002?",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_successful_refund_check_allows_checked_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_refund_status\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_found: True\n"
            "- refund_found: True\n"
            "- order_number: ORD-10003\n"
            "- refund_number: REF-10003\n"
            "- status: processing\n"
            "- amount: 1299.00\n"
            "- currency: INR"
        ),
        tool_used=True,
        tool_name="get_refund_status",
        tool_success=True,
    )

    result = validator.validate(
        response_text=("I've checked the refund status. The refund is processing."),
        query=("Where is my refund for ORD-10003?"),
        verified_knowledge=(verified_knowledge),
        system_capabilities=(system_capabilities),
        operational_context=(operational_context),
    )

    assert result.is_valid


def test_failed_refund_check_rejects_checked_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_refund_status\n"
            "Tool status: failed\n"
            "Data: "
            "{'order_number': 'ORD-99999'}\n"
            "Error: Order not found."
        ),
        tool_used=True,
        tool_name="get_refund_status",
        tool_success=False,
    )

    result = validator.validate(
        response_text=("I've checked the refund status."),
        query=("Where is my refund for ORD-99999?"),
        verified_knowledge=(verified_knowledge),
        system_capabilities=(system_capabilities),
        operational_context=(operational_context),
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_refund_amount_from_operational_data_is_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):
    operational_context = OperationalContext(
        context=(
            "Tool: get_refund_status\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- refund_found: True\n"
            "- status: processing\n"
            "- amount: 1299.00\n"
            "- currency: INR"
        ),
        tool_used=True,
        tool_name="get_refund_status",
        tool_success=True,
    )

    result = validator.validate(
        response_text=("The refund amount is ₹1299.00 and its status is processing."),
        query=("What is the refund status for ORD-10003?"),
        verified_knowledge=(verified_knowledge),
        system_capabilities=(system_capabilities),
        operational_context=(operational_context),
    )

    assert result.is_valid


def test_numeric_claim_from_successful_multi_tool_data_is_allowed(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=True,
            data={
                "order_number": "ORD-10003",
                "refund_found": True,
                "refund_number": "REF-10003",
                "status": "processing",
                "amount": "3899.00",
                "currency": "INR",
            },
        ),
    )

    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- status: delivered\n"
            "\n"
            "Tool: get_refund_status\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- refund_found: True\n"
            "- refund_number: REF-10003\n"
            "- status: processing\n"
            "- amount: 3899.00\n"
            "- currency: INR"
        ),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )

    result = validator.validate(
        response_text=("ORD-10003 is delivered and its ₹3899.00 refund is processing."),
        query=("What is the order status and refund status for ORD-10003?"),
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_numeric_claim_from_failed_tool_in_multi_tool_run_is_rejected(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=False,
            data={
                "order_number": "ORD-10003",
                "amount": "3899.00",
                "currency": "INR",
            },
            error="Refund lookup failed.",
        ),
    )

    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- status: delivered\n"
            "\n"
            "Tool: get_refund_status\n"
            "Tool status: failed\n"
            "Data: {'amount': '3899.00', "
            "'currency': 'INR'}\n"
            "Error: Refund lookup failed."
        ),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )

    result = validator.validate(
        response_text=("The refund amount is ₹3899.00."),
        query=("What is the order status and refund status for ORD-10003?"),
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_numeric_claim" for issue in result.issues)


def test_successful_multi_tool_checks_allow_checked_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=True,
            data={
                "order_number": "ORD-10003",
                "refund_found": True,
                "status": "processing",
            },
        ),
    )

    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- status: delivered\n"
            "\n"
            "Tool: get_refund_status\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- refund_found: True\n"
            "- status: processing"
        ),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )

    result = validator.validate(
        response_text=(
            "I've checked the order and refund status. "
            "The order is delivered and the refund "
            "is processing."
        ),
        query=("What is the order status and refund status for ORD-10003?"),
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_failed_tool_in_multi_tool_run_rejects_checked_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=False,
            data={
                "order_number": "ORD-10003",
            },
            error="Refund lookup failed.",
        ),
    )

    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- status: delivered\n"
            "\n"
            "Tool: get_refund_status\n"
            "Tool status: failed\n"
            "Data: {'order_number': 'ORD-10003'}\n"
            "Error: Refund lookup failed."
        ),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )

    result = validator.validate(
        response_text=(
            "I've checked the order and refund status. The order is delivered."
        ),
        query=("What is the order status and refund status for ORD-10003?"),
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_successful_multi_tool_lookup_allows_looked_up_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=True,
            data={
                "order_number": "ORD-10003",
                "refund_found": True,
                "status": "processing",
            },
        ),
    )

    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- status: delivered\n"
            "\n"
            "Tool: get_refund_status\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- refund_found: True\n"
            "- status: processing"
        ),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )

    result = validator.validate(
        response_text=(
            "I've looked up the order and refund status. "
            "The order is delivered and the refund "
            "is processing."
        ),
        query=("What is the order status and refund status for ORD-10003?"),
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid


def test_failed_lookup_in_multi_tool_run_rejects_looked_up_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_results = (
        ToolResult(
            tool_name="get_order",
            success=True,
            data={
                "order_number": "ORD-10003",
                "status": "delivered",
            },
        ),
        ToolResult(
            tool_name="get_refund_status",
            success=False,
            data={
                "order_number": "ORD-10003",
            },
            error="Refund lookup failed.",
        ),
    )

    operational_context = OperationalContext(
        context=(
            "Tool: get_order\n"
            "Tool status: success\n"
            "Authoritative operational data:\n"
            "- order_number: ORD-10003\n"
            "- status: delivered\n"
            "\n"
            "Tool: get_refund_status\n"
            "Tool status: failed\n"
            "Data: {'order_number': 'ORD-10003'}\n"
            "Error: Refund lookup failed."
        ),
        tool_used=True,
        tool_name=None,
        tool_success=None,
        tool_results=tool_results,
    )

    result = validator.validate(
        response_text=(
            "I've looked up the order and refund status. The order is delivered."
        ),
        query=("What is the order status and refund status for ORD-10003?"),
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert not result.is_valid

    assert any(issue.code == "unsupported_action_claim" for issue in result.issues)


def test_refund_eligibility_rejects_premature_processing_claim(
    validator,
    verified_knowledge,
    system_capabilities,
):
    tool_result = ToolResult(
        tool_name="check_refund_eligibility",
        success=True,
        data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "reason_code": "eligible",
            "refund_amount": "1299.00",
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    operational_context = build_operational_context(tool_result)

    response = (
        "Order ORD-10002 is eligible for a refund. "
        "The refund is currently in a processing state "
        "and requires your confirmation before it can be completed."
    )

    result = validator.validate(
        response_text=response,
        query="I want to initiate a refund for order ORD-10002.",
        verified_knowledge=verified_knowledge,
        system_capabilities=system_capabilities,
        operational_context=operational_context,
    )

    assert result.is_valid is False

    assert any(
        issue.code == "unsupported_refund_state_claim" for issue in result.issues
    )
