from decimal import Decimal

import src.tools.refund_eligibility_tool as module
from src.tools.refund_eligibility import (
    RefundEligibilityResult,
)


def test_database_session_failure_returns_safe_error(
    monkeypatch,
):
    def failing_session():
        raise RuntimeError("Internal database connection details")

    monkeypatch.setattr(
        module,
        "SessionLocal",
        failing_session,
    )

    tool = module.RefundEligibilityTool()

    result = tool.execute("ORD-10002")

    assert result.tool_name == ("check_refund_eligibility")

    assert result.success is False

    assert result.data == {
        "order_number": "ORD-10002",
    }

    assert result.error == ("Refund eligibility check failed.")

    assert "Internal database connection details" not in str(result)


def test_eligible_refund_returns_serialized_tool_result(
    monkeypatch,
):
    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    session = FakeSession()

    monkeypatch.setattr(
        module,
        "SessionLocal",
        lambda: session,
    )

    def fake_check_refund_eligibility(
        db,
        order_number,
    ):
        assert db is session
        assert order_number == "ORD-10002"

        return RefundEligibilityResult(
            found=True,
            order_number="ORD-10002",
            status="processing",
            payment_status="paid",
            eligible=True,
            reason_code="ELIGIBLE",
            reason=("The order is eligible for a full refund."),
            refund_amount=Decimal("1299.00"),
            currency="INR",
            requires_confirmation=True,
            action_performed=False,
        )

    monkeypatch.setattr(
        module,
        "check_refund_eligibility",
        fake_check_refund_eligibility,
    )

    tool = module.RefundEligibilityTool()

    result = tool.execute("ORD-10002")

    assert result.tool_name == "check_refund_eligibility"

    assert result.success is True
    assert result.error is None

    assert result.data == {
        "found": True,
        "order_number": "ORD-10002",
        "status": "processing",
        "payment_status": "paid",
        "eligible": True,
        "reason_code": "ELIGIBLE",
        "reason": ("The order is eligible for a full refund."),
        "refund_amount": "1299.00",
        "currency": "INR",
        "requires_confirmation": True,
        "action_performed": False,
    }

    assert session.closed is True
