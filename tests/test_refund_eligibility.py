import src.tools.refund_eligibility as module
from src.tools.order_lookup import OrderLookupResult


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
