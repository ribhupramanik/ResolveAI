import src.tools.cancellation_eligibility as module
from src.tools.order_lookup import (
    OrderLookupResult,
)


def test_processing_order_is_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10002",
            status="processing",
        ),
    )

    result = module.check_cancellation_eligibility(
        object(),
        "ORD-10002",
    )

    assert result.found is True
    assert result.eligible is True
    assert result.requires_confirmation is True
    assert result.action_performed is False


def test_shipped_order_is_not_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10001",
            status="shipped",
        ),
    )

    result = module.check_cancellation_eligibility(
        object(),
        "ORD-10001",
    )

    assert result.found is True
    assert result.eligible is False
    assert result.requires_confirmation is False
    assert result.action_performed is False


def test_delivered_order_is_not_eligible(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_order",
        lambda db, order_number: OrderLookupResult(
            found=True,
            order_number="ORD-10003",
            status="delivered",
        ),
    )

    result = module.check_cancellation_eligibility(
        object(),
        "ORD-10003",
    )

    assert result.found is True
    assert result.eligible is False


def test_unknown_order_is_not_found(
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

    result = module.check_cancellation_eligibility(
        object(),
        "ORD-99999",
    )

    assert result.found is False
    assert result.eligible is None
    assert result.requires_confirmation is False
    assert result.action_performed is False
