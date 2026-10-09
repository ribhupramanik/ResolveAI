from types import SimpleNamespace

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
