from types import SimpleNamespace

import pytest

import src.services.pending_action_integration as module


def test_eligible_refund_creates_pending_action(
    monkeypatch,
):
    captured = {}

    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            assert session is db

        def create_pending_action(self, **kwargs):
            captured.update(kwargs)

            return SimpleNamespace(
                **kwargs,
                status="pending",
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=False,
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "reason_code": "ELIGIBLE",
            "refund_amount": "1299.00",
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is not None
    assert pending_action.status == "pending"

    assert captured["conversation_id"] == 42

    assert captured["action_type"] == ("initiate_refund")

    assert captured["target_type"] == "order"

    assert captured["target_identifier"] == ("ORD-10002")

    action_data = captured["action_data"]

    assert action_data["refund_amount"] == "1299.00"
    assert action_data["currency"] == "INR"

    assert action_data["eligible"] is True

    assert action_data["requires_confirmation"] is True

    assert action_data["action_performed"] is False


def test_ineligible_refund_does_not_create_pending_action(
    monkeypatch,
):
    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            raise AssertionError(
                "PendingActionService must not be created for an ineligible refund."
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=False,
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "delivered",
            "payment_status": "paid",
            "eligible": False,
            "reason_code": "REFUND_ALREADY_COMPLETED",
            "reason": "This order has already been refunded.",
            "refund_amount": None,
            "currency": None,
            "requires_confirmation": False,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is None


def test_failed_refund_tool_does_not_create_pending_action(
    monkeypatch,
):
    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            raise AssertionError(
                "PendingActionService must not be created "
                "when refund eligibility tool fails."
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=False,
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=False,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "refund_amount": "1299.00",
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is None


def test_refund_fallback_does_not_create_pending_action(
    monkeypatch,
):
    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            raise AssertionError(
                "PendingActionService must not be created "
                "when the RAG pipeline uses fallback."
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=True,
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "refund_amount": "1299.00",
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is None


def test_incorrect_tool_does_not_create_refund_pending_action(
    monkeypatch,
):
    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            raise AssertionError(
                "PendingActionService must not be created "
                "for an incorrect operational tool."
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=False,
        tool_used=True,
        tool_name="get_refund_status",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "refund_amount": "1299.00",
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is None


@pytest.mark.parametrize(
    "refund_amount",
    [
        "0.00",
        "-1299.00",
        "NaN",
        "Infinity",
        "1299.999",
        "invalid",
        "1e3",
        "",
    ],
)
def test_invalid_refund_amount_does_not_create_pending_action(
    monkeypatch,
    refund_amount,
):
    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            raise AssertionError(
                "PendingActionService must not be created "
                "when the refund amount is invalid."
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=False,
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "refund_amount": refund_amount,
            "currency": "INR",
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is None


@pytest.mark.parametrize(
    "currency",
    [
        None,
        123,
        "",
        "IN",
        "INRR",
        "IN1",
        "₹",
        "IN R",
    ],
)
def test_invalid_refund_currency_does_not_create_pending_action(
    monkeypatch,
    currency,
):
    db = object()

    class FakePendingActionService:
        def __init__(self, session):
            raise AssertionError(
                "PendingActionService must not be created "
                "when the refund currency is invalid."
            )

    monkeypatch.setattr(
        module,
        "PendingActionService",
        FakePendingActionService,
    )

    result = SimpleNamespace(
        used_fallback=False,
        tool_used=True,
        tool_name="check_refund_eligibility",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "payment_status": "paid",
            "eligible": True,
            "refund_amount": "1299.00",
            "currency": currency,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    pending_action = module.maybe_create_pending_refund(
        db=db,
        conversation_id=42,
        result=result,
    )

    assert pending_action is None
