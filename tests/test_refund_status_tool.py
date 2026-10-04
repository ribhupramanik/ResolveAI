from datetime import datetime, timezone
from decimal import Decimal

from src.tools.refund_status import (
    RefundStatusResult,
)
from src.tools.refund_status_tool import (
    RefundStatusTool,
)


class DummySession:
    def close(self):
        pass


def test_refund_status_tool_returns_refund(
    monkeypatch,
):
    def fake_get_refund_status(
        db,
        order_number,
    ):
        assert order_number == "ORD-10002"

        return RefundStatusResult(
            order_found=True,
            refund_found=True,
            order_number="ORD-10002",
            refund_number="REF-10002",
            status="processing",
            amount=Decimal("1299.00"),
            currency="INR",
            initiated_at=datetime(
                2026,
                10,
                1,
                10,
                30,
                tzinfo=timezone.utc,
            ),
            completed_at=None,
            failure_reason=None,
        )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.SessionLocal",
        lambda: DummySession(),
    )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.get_refund_status",
        fake_get_refund_status,
    )

    result = RefundStatusTool().execute("ORD-10002")

    assert result.tool_name == ("get_refund_status")

    assert result.success is True
    assert result.error is None

    assert result.data == {
        "order_found": True,
        "refund_found": True,
        "order_number": "ORD-10002",
        "refund_number": "REF-10002",
        "status": "processing",
        "amount": "1299.00",
        "currency": "INR",
        "initiated_at": ("2026-10-01T10:30:00+00:00"),
        "completed_at": None,
        "failure_reason": None,
    }


def test_refund_status_tool_reports_no_refund(
    monkeypatch,
):
    def fake_get_refund_status(
        db,
        order_number,
    ):
        return RefundStatusResult(
            order_found=True,
            refund_found=False,
            order_number="ORD-10002",
        )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.SessionLocal",
        lambda: DummySession(),
    )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.get_refund_status",
        fake_get_refund_status,
    )

    result = RefundStatusTool().execute("ORD-10002")

    assert result.tool_name == ("get_refund_status")

    assert result.success is True
    assert result.error is None

    assert result.data == {
        "order_found": True,
        "refund_found": False,
        "order_number": "ORD-10002",
    }


def test_refund_status_tool_reports_unknown_order(
    monkeypatch,
):
    def fake_get_refund_status(
        db,
        order_number,
    ):
        return RefundStatusResult(
            order_found=False,
            refund_found=False,
            order_number="ORD-99999",
        )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.SessionLocal",
        lambda: DummySession(),
    )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.get_refund_status",
        fake_get_refund_status,
    )

    result = RefundStatusTool().execute("ORD-99999")

    assert result.tool_name == ("get_refund_status")

    assert result.success is False

    assert result.data == {
        "order_found": False,
        "refund_found": False,
        "order_number": "ORD-99999",
    }

    assert result.error == ("Order not found.")


def test_refund_status_tool_handles_failure(
    monkeypatch,
):
    def failing_get_refund_status(
        db,
        order_number,
    ):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "src.tools.refund_status_tool.SessionLocal",
        lambda: DummySession(),
    )

    monkeypatch.setattr(
        "src.tools.refund_status_tool.get_refund_status",
        failing_get_refund_status,
    )

    result = RefundStatusTool().execute("ORD-10002")

    assert result.tool_name == ("get_refund_status")

    assert result.success is False

    assert result.data == {
        "order_number": "ORD-10002",
    }

    assert result.error == ("Refund status lookup failed.")
