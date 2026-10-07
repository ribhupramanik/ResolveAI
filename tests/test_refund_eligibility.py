from decimal import Decimal

import src.tools.refund_eligibility as module
from src.tools.order_lookup import OrderLookupResult


class EmptyRefundScalarResult:
    def all(self):
        return []


class FakeRefundSession:
    def scalars(
        self,
        statement,
    ):
        return EmptyRefundScalarResult()


def test_unknown_order_is_not_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=False,
            order_number="ORD-99999",
        ),
    )

    result = module.check_refund_eligibility(
        object(),
        "ORD-99999",
    )

    assert result.found is False
    assert result.order_number == "ORD-99999"

    assert result.eligible is None

    assert result.reason_code == "ORDER_NOT_FOUND"
    assert result.reason == "Order not found."

    assert result.requires_confirmation is False
    assert result.action_performed is False


def test_unpaid_order_is_not_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10004",
            status="processing",
            payment_status="unpaid",
        ),
    )

    result = module.check_refund_eligibility(
        object(),
        "ORD-10004",
    )

    assert result.found is True
    assert result.order_number == "ORD-10004"

    assert result.eligible is False

    assert result.reason_code == "ORDER_NOT_PAID"
    assert result.reason == "The order has not been paid."

    assert result.requires_confirmation is False
    assert result.action_performed is False


def test_paid_processing_order_without_refund_is_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10002",
            status="processing",
            payment_status="paid",
            total_amount=Decimal("1299.00"),
            currency="INR",
        ),
    )

    result = module.check_refund_eligibility(
        FakeRefundSession(),
        "ORD-10002",
    )

    assert result.found is True
    assert result.order_number == "ORD-10002"

    assert result.status == "processing"
    assert result.payment_status == "paid"

    assert result.eligible is True

    assert result.reason_code == "ELIGIBLE"
    assert result.reason == ("The order is eligible for a full refund.")

    assert result.refund_amount == Decimal("1299.00")
    assert result.currency == "INR"

    assert result.requires_confirmation is True
    assert result.action_performed is False


def test_paid_shipped_order_is_not_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10001",
            status="shipped",
            payment_status="paid",
            total_amount=Decimal("2499.00"),
            currency="INR",
        ),
    )

    result = module.check_refund_eligibility(
        FakeRefundSession(),
        "ORD-10001",
    )

    assert result.found is True
    assert result.order_number == "ORD-10001"

    assert result.status == "shipped"
    assert result.payment_status == "paid"

    assert result.eligible is False

    assert result.reason_code == "ORDER_SHIPPED"
    assert result.reason == (
        "The order has already shipped and is not eligible for a direct refund."
    )

    assert result.refund_amount is None
    assert result.currency is None

    assert result.requires_confirmation is False
    assert result.action_performed is False


def test_paid_delivered_order_without_refund_is_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10005",
            status="delivered",
            payment_status="paid",
            total_amount=Decimal("3899.00"),
            currency="INR",
        ),
    )

    result = module.check_refund_eligibility(
        FakeRefundSession(),
        "ORD-10005",
    )

    assert result.found is True
    assert result.order_number == "ORD-10005"

    assert result.status == "delivered"
    assert result.payment_status == "paid"

    assert result.eligible is True
    assert result.reason_code == "ELIGIBLE"
    assert result.reason == ("The order is eligible for a full refund.")

    assert result.refund_amount == Decimal("3899.00")
    assert result.currency == "INR"

    assert result.requires_confirmation is True
    assert result.action_performed is False


def test_paid_cancelled_order_without_refund_is_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10006",
            status="cancelled",
            payment_status="paid",
            total_amount=Decimal("1999.00"),
            currency="INR",
        ),
    )

    result = module.check_refund_eligibility(
        FakeRefundSession(),
        "ORD-10006",
    )

    assert result.found is True
    assert result.order_number == "ORD-10006"

    assert result.status == "cancelled"
    assert result.payment_status == "paid"

    assert result.eligible is True

    assert result.reason_code == "ELIGIBLE"
    assert result.reason == ("The order is eligible for a full refund.")

    assert result.refund_amount == Decimal("1999.00")
    assert result.currency == "INR"

    assert result.requires_confirmation is True
    assert result.action_performed is False


class RefundStatusScalarResult:
    def __init__(self, statuses):
        self.statuses = statuses

    def all(self):
        return self.statuses


class RefundStatusSession:
    def __init__(self, statuses):
        self.statuses = statuses

    def scalars(
        self,
        statement,
    ):
        return RefundStatusScalarResult(self.statuses)


def test_existing_processing_refund_blocks_new_refund(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10003",
            status="delivered",
            payment_status="paid",
            total_amount=Decimal("3899.00"),
            currency="INR",
        ),
    )

    result = module.check_refund_eligibility(
        RefundStatusSession(["processing"]),
        "ORD-10003",
    )

    assert result.found is True
    assert result.order_number == "ORD-10003"

    assert result.status == "delivered"
    assert result.payment_status == "paid"

    assert result.eligible is False

    assert result.reason_code == ("REFUND_ALREADY_PROCESSING")
    assert result.reason == ("A refund is already being processed for this order.")

    assert result.refund_amount is None
    assert result.currency is None

    assert result.requires_confirmation is False
    assert result.action_performed is False


def test_existing_completed_refund_blocks_new_refund(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10007",
            status="delivered",
            payment_status="paid",
            total_amount=Decimal("1599.00"),
            currency="INR",
        ),
    )

    result = module.check_refund_eligibility(
        RefundStatusSession(["completed"]),
        "ORD-10007",
    )

    assert result.found is True
    assert result.order_number == "ORD-10007"

    assert result.status == "delivered"
    assert result.payment_status == "paid"

    assert result.eligible is False

    assert result.reason_code == ("REFUND_ALREADY_COMPLETED")
    assert result.reason == ("This order has already been refunded.")

    assert result.refund_amount is None
    assert result.currency is None

    assert result.requires_confirmation is False
    assert result.action_performed is False
