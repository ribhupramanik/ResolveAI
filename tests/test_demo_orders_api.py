from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from src.api.main import app
from src.db.database import SessionLocal, engine
from src.db.models import Conversation, Customer, Order, PendingAction, Refund


def test_demo_orders_list_returns_database_orders():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-DEMO-{token[:12]}",
                name="Demo Order Customer",
                email=f"demo-order-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            order = Order(
                order_number=order_number,
                customer_id=customer.id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Demo Test Address",
            )

            db.add(order)
            db.flush()

            customer_id = customer.id
            order_id = order.id

            db.commit()

        client = TestClient(app)

        response = client.get("/api/v1/demo/orders")

        assert response.status_code == 200

        data = response.json()

        assert isinstance(data, list)

        matching_orders = [
            item for item in data if item["order_number"] == order_number
        ]

        assert len(matching_orders) == 1

        result = matching_orders[0]

        assert result["id"] == order_id
        assert result["customer_id"] == customer_id
        assert result["customer_name"] == "Demo Order Customer"
        assert result["status"] == "processing"
        assert result["payment_status"] == "paid"
        assert Decimal(str(result["total_amount"])) == Decimal("1299.00")
        assert result["currency"] == "INR"

    finally:
        if order_id is not None:
            with SessionLocal() as db:
                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


def test_demo_orders_create_persists_order():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        customer = Customer(
            customer_code=f"TST-CREATE-{token[:12]}",
            name="Demo Creation Customer",
            email=f"demo-create-{token}@example.com",
        )

        db.add(customer)
        db.flush()

        customer_id = customer.id

        db.commit()

    try:
        request_data = {
            "order_number": order_number,
            "customer_id": customer_id,
            "status": "processing",
            "payment_status": "paid",
            "total_amount": "2499.00",
            "currency": "INR",
            "shipping_address": "Kolkata, West Bengal",
            "carrier": None,
            "tracking_number": None,
            "estimated_delivery": None,
        }

        client = TestClient(app)

        response = client.post(
            "/api/v1/demo/orders",
            json=request_data,
        )

        assert response.status_code == 201, response.text

        data = response.json()

        assert data["id"] > 0
        assert data["order_number"] == order_number
        assert data["customer_id"] == customer_id
        assert data["customer_name"] == "Demo Creation Customer"
        assert data["status"] == "processing"
        assert data["payment_status"] == "paid"
        assert Decimal(str(data["total_amount"])) == Decimal("2499.00")
        assert data["currency"] == "INR"
        assert data["shipping_address"] == "Kolkata, West Bengal"

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.scalar(
                select(Order).where(Order.order_number == order_number)
            )

            assert stored_order is not None
            assert stored_order.id == data["id"]
            assert stored_order.customer_id == customer_id
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("2499.00")
            assert stored_order.currency == "INR"
            assert stored_order.shipping_address == "Kolkata, West Bengal"

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            db.execute(delete(Order).where(Order.order_number == order_number))

            db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("status", "teleported"),
        ("payment_status", "unknown"),
    ],
)
def test_demo_order_create_rejects_invalid_statuses(
    field,
    invalid_value,
):
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        customer = Customer(
            customer_code=f"TST-STATUS-{token[:12]}",
            name="Status Validation Customer",
            email=f"status-validation-{token}@example.com",
        )

        db.add(customer)
        db.commit()

        customer_id = customer.id

    try:
        payload = {
            "order_number": order_number,
            "customer_id": customer_id,
            "status": "processing",
            "payment_status": "paid",
            "total_amount": "1499.00",
            "currency": "INR",
            "shipping_address": "Kolkata, West Bengal",
        }

        payload[field] = invalid_value

        client = TestClient(app)

        response = client.post(
            "/api/v1/demo/orders",
            json=payload,
        )

        assert response.status_code == 422, response.text

        with SessionLocal() as db:
            assert (
                db.scalar(select(Order.id).where(Order.order_number == order_number))
                is None
            )

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            db.execute(delete(Order).where(Order.order_number == order_number))

            db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_create_rejects_duplicate_order_number():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-DUP-{token[:12]}",
                name="Duplicate Order Customer",
                email=f"duplicate-order-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            db.commit()

        payload = {
            "order_number": order_number,
            "customer_id": customer_id,
            "status": "processing",
            "payment_status": "paid",
            "total_amount": "2499.00",
            "currency": "INR",
            "shipping_address": "Kolkata, West Bengal",
        }

        with TestClient(app) as client:
            first_response = client.post(
                "/api/v1/demo/orders",
                json=payload,
            )

            assert first_response.status_code == 201, first_response.text

            duplicate_response = client.post(
                "/api/v1/demo/orders",
                json={
                    **payload,
                    "total_amount": "9999.00",
                },
            )

        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["detail"] == ("Order number already exists.")

        with SessionLocal() as db:
            stored_orders = db.scalars(
                select(Order).where(Order.order_number == order_number)
            ).all()

            assert len(stored_orders) == 1
            assert stored_orders[0].total_amount == Decimal("2499.00")

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            db.execute(delete(Order).where(Order.order_number == order_number))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_create_rejects_missing_customer():
    assert engine.url.database == "resolveai_test"

    order_number = f"ORD-{uuid4().int % 10**18:018d}"
    missing_customer_id = 2_000_000_000

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        assert db.get(Customer, missing_customer_id) is None

    payload = {
        "order_number": order_number,
        "customer_id": missing_customer_id,
        "status": "processing",
        "payment_status": "paid",
        "total_amount": "1499.00",
        "currency": "INR",
        "shipping_address": "Kolkata, West Bengal",
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/orders",
            json=payload,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found."

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        stored_order = db.scalar(
            select(Order).where(Order.order_number == order_number)
        )

        assert stored_order is None


def test_demo_orders_update_persists_status_change():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-UPDATE-{token[:12]}",
                name="Demo Update Customer",
                email=f"demo-update-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
            )

            db.add(order)
            db.flush()

            order_id = order.id

            db.commit()

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/demo/orders/{order_id}",
                json={
                    "status": "shipped",
                },
            )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["id"] == order_id
        assert data["order_number"] == order_number
        assert data["status"] == "shipped"
        assert data["payment_status"] == "paid"
        assert Decimal(str(data["total_amount"])) == Decimal("2499.00")
        assert data["customer_id"] == customer_id

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)

            assert stored_order is not None
            assert stored_order.status == "shipped"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("2499.00")
            assert stored_order.order_number == order_number

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_update_rejects_missing_order():
    assert engine.url.database == "resolveai_test"

    missing_order_id = 2_000_000_000

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        assert db.get(Order, missing_order_id) is None

    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/demo/orders/{missing_order_id}",
            json={
                "status": "shipped",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."


def test_demo_orders_update_rejects_invalid_fields():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-VALID-{token[:12]}",
                name="Update Validation Customer",
                email=f"update-validation-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
            )

            db.add(order)
            db.flush()

            order_id = order.id

            db.commit()

        invalid_payloads = [
            {"status": "teleported"},
            {"payment_status": "unknown"},
            {"order_number": "ORD-99999"},
            {"total_amount": "0.00"},
            {"status": None},
            {"shipping_address": None},
            {},
        ]

        with TestClient(app) as client:
            for payload in invalid_payloads:
                response = client.patch(
                    f"/api/v1/demo/orders/{order_id}",
                    json=payload,
                )

                assert response.status_code == 422, (
                    f"Payload: {payload}, Response: {response.text}"
                )

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)

            assert stored_order is not None
            assert stored_order.order_number == order_number
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("2499.00")
            assert stored_order.shipping_address == "Kolkata, West Bengal"

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_update_rejects_order_with_pending_action():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    conversation_id = None
    order_id = None
    action_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-PEND-{token[:12]}",
                name="Pending Action Customer",
                email=f"pending-action-{token}@example.com",
            )

            conversation = Conversation(
                title="Pending Action Safety Test",
            )

            db.add_all([customer, conversation])
            db.flush()

            customer_id = customer.id
            conversation_id = conversation.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
            )

            db.add(order)
            db.flush()

            order_id = order.id

            action = PendingAction(
                conversation_id=conversation_id,
                action_type="cancel_order",
                target_type="order",
                target_identifier=order_number,
                status="pending",
                action_data={
                    "order_status": "processing",
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            db.add(action)
            db.flush()

            action_id = action.id

            db.commit()

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/demo/orders/{order_id}",
                json={
                    "status": "shipped",
                },
            )

        assert response.status_code == 409, response.text

        assert response.json()["detail"] == (
            "This order has an active or executed action "
            "and cannot be modified through the demo manager."
        )

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)
            stored_action = db.get(PendingAction, action_id)

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("2499.00")

            assert stored_action is not None
            assert stored_action.status == "pending"
            assert stored_action.target_identifier == order_number

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if action_id is not None:
                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if conversation_id is not None:
                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_update_rejects_order_with_refund_history():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None
    refund_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-RH-{token[:12]}",
                name="Refund History Customer",
                email=f"refund-history-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
            )

            db.add(order)
            db.flush()

            order_id = order.id

            refund = Refund(
                refund_number=f"REF-{token.upper()}",
                order_id=order_id,
                status="processing",
                amount=Decimal("2499.00"),
                currency="INR",
                initiated_at=datetime.now(UTC),
            )

            db.add(refund)
            db.flush()

            refund_id = refund.id

            db.commit()

        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/demo/orders/{order_id}",
                json={
                    "total_amount": "9999.00",
                },
            )

        assert response.status_code == 409, response.text

        assert response.json()["detail"] == (
            "This order has refund history "
            "and cannot be modified through the demo manager."
        )

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)
            stored_refund = db.get(Refund, refund_id)

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"
            assert stored_order.total_amount == Decimal("2499.00")

            assert stored_refund is not None
            assert stored_refund.status == "processing"
            assert stored_refund.amount == Decimal("2499.00")
            assert stored_refund.order_id == order_id

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if refund_id is not None:
                db.execute(delete(Refund).where(Refund.id == refund_id))

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_delete_removes_created_order():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-DELETE-{token[:12]}",
                name="Demo Delete Customer",
                email=f"demo-delete-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            db.commit()

        payload = {
            "order_number": order_number,
            "customer_id": customer_id,
            "status": "processing",
            "payment_status": "paid",
            "total_amount": "2499.00",
            "currency": "INR",
            "shipping_address": "Kolkata, West Bengal",
        }

        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/demo/orders",
                json=payload,
            )

            assert create_response.status_code == 201, create_response.text

            assert create_response.json()["is_demo_managed"] is True

            order_id = create_response.json()["id"]

            delete_response = client.delete(f"/api/v1/demo/orders/{order_id}")

        assert delete_response.status_code == 204, delete_response.text

        assert delete_response.content == b""

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)

            assert stored_order is None

            stored_customer = db.get(Customer, customer_id)

            assert stored_customer is not None
            assert stored_customer.name == "Demo Delete Customer"

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            db.execute(delete(Order).where(Order.order_number == order_number))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_delete_rejects_seeded_order():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-SEED-{token[:12]}",
                name="Protected Seeded Customer",
                email=f"protected-seed-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
                is_demo_managed=False,
            )

            db.add(order)
            db.flush()

            order_id = order.id

            db.commit()

        with TestClient(app) as client:
            response = client.delete(f"/api/v1/demo/orders/{order_id}")

        assert response.status_code == 403, response.text

        assert response.json()["detail"] == ("Only demo-managed orders can be deleted.")

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)

            assert stored_order is not None
            assert stored_order.order_number == order_number
            assert stored_order.is_demo_managed is False
            assert stored_order.status == "processing"
            assert stored_order.total_amount == Decimal("2499.00")

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


@pytest.mark.parametrize(
    "action_status",
    [
        "pending",
        "rejected",
        "executed",
    ],
)
def test_demo_orders_delete_rejects_order_with_action_history(
    action_status,
):
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    conversation_id = None
    order_id = None
    action_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-DACT-{token[:12]}",
                name="Delete Action History Customer",
                email=f"delete-action-{token}@example.com",
            )

            conversation = Conversation(
                title="Delete Action History Test",
            )

            db.add_all([customer, conversation])
            db.flush()

            customer_id = customer.id
            conversation_id = conversation.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
                is_demo_managed=True,
            )

            db.add(order)
            db.flush()

            order_id = order.id

            action = PendingAction(
                conversation_id=conversation_id,
                action_type="cancel_order",
                target_type="order",
                target_identifier=order_number,
                status=action_status,
                action_data={
                    "order_status": "processing",
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            db.add(action)
            db.flush()

            action_id = action.id

            db.commit()

        with TestClient(app) as client:
            response = client.delete(f"/api/v1/demo/orders/{order_id}")

        assert response.status_code == 409, response.text

        assert response.json()["detail"] == (
            "This order has action history and cannot be deleted."
        )

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)
            stored_action = db.get(PendingAction, action_id)

            assert stored_order is not None
            assert stored_order.is_demo_managed is True
            assert stored_order.status == "processing"
            assert stored_order.total_amount == Decimal("2499.00")

            assert stored_action is not None
            assert stored_action.status == action_status
            assert stored_action.target_identifier == order_number

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if action_id is not None:
                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if conversation_id is not None:
                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


@pytest.mark.parametrize(
    "refund_status",
    [
        "processing",
        "completed",
        "failed",
    ],
)
def test_demo_orders_delete_rejects_order_with_refund_history(
    refund_status,
):
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None
    refund_id = None

    try:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            customer = Customer(
                customer_code=f"TST-DRFD-{token[:12]}",
                name="Refund Deletion Test Customer",
                email=f"refund-delete-{token}@example.com",
            )

            db.add(customer)
            db.flush()

            customer_id = customer.id

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("2499.00"),
                currency="INR",
                shipping_address="Kolkata, West Bengal",
                is_demo_managed=True,
            )

            db.add(order)
            db.flush()

            order_id = order.id

            refund = Refund(
                refund_number=f"REF-{token.upper()}",
                order_id=order_id,
                status=refund_status,
                amount=Decimal("2499.00"),
                currency="INR",
                initiated_at=datetime.now(UTC),
            )

            db.add(refund)
            db.flush()

            refund_id = refund.id

            db.commit()

        with TestClient(app) as client:
            response = client.delete(f"/api/v1/demo/orders/{order_id}")

        assert response.status_code == 409, response.text

        assert response.json()["detail"] == (
            "This order has refund history and cannot be deleted."
        )

        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            stored_order = db.get(Order, order_id)
            stored_refund = db.get(Refund, refund_id)

            assert stored_order is not None
            assert stored_order.is_demo_managed is True
            assert stored_order.order_number == order_number
            assert stored_order.status == "processing"
            assert stored_order.total_amount == Decimal("2499.00")

            assert stored_refund is not None
            assert stored_refund.order_id == order_id
            assert stored_refund.status == refund_status
            assert stored_refund.amount == Decimal("2499.00")

    finally:
        with SessionLocal() as db:
            assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

            if refund_id is not None:
                db.execute(delete(Refund).where(Refund.id == refund_id))

            if order_id is not None:
                db.execute(delete(Order).where(Order.id == order_id))

            if customer_id is not None:
                db.execute(delete(Customer).where(Customer.id == customer_id))

            db.commit()


def test_demo_orders_delete_rejects_missing_order():
    assert engine.url.database == "resolveai_test"

    missing_order_id = 2_000_000_000

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        assert db.get(Order, missing_order_id) is None

    with TestClient(app) as client:
        response = client.delete(f"/api/v1/demo/orders/{missing_order_id}")

    assert response.status_code == 404, response.text

    assert response.json() == {"detail": "Order not found."}

    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "resolveai_test"

        assert db.get(Order, missing_order_id) is None


def test_demo_orders_create_automatically_creates_customer():
    assert engine.url.database == "resolveai_test"

    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    order_id = None
    customer_id = None

    try:
        payload = {
            "order_number": order_number,
            "status": "processing",
            "payment_status": "paid",
            "total_amount": "2499.00",
            "currency": "INR",
            "shipping_address": "Kolkata, West Bengal",
        }

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/demo/orders",
                json=payload,
            )

        assert response.status_code == 201, response.text

        data = response.json()

        order_id = data["id"]
        customer_id = data["customer_id"]

        assert data["order_number"] == order_number
        assert data["is_demo_managed"] is True
        assert data["customer_name"]

        with SessionLocal() as db:
            assert (
                db.scalar(text("SELECT current_database()"))
                == "resolveai_test"
            )

            stored_order = db.get(Order, order_id)
            stored_customer = db.get(Customer, customer_id)

            assert stored_order is not None
            assert stored_customer is not None

            assert stored_order.customer_id == stored_customer.id
            assert stored_order.is_demo_managed is True

            assert stored_customer.name == data["customer_name"]
            assert stored_customer.customer_code
            assert stored_customer.email

    finally:
        with SessionLocal() as db:
            assert (
                db.scalar(text("SELECT current_database()"))
                == "resolveai_test"
            )

            if order_id is None:
                existing_order = db.scalar(
                    select(Order).where(
                        Order.order_number == order_number
                    )
                )

                if existing_order is not None:
                    order_id = existing_order.id
                    customer_id = existing_order.customer_id

            if order_id is not None:
                db.execute(
                    delete(Order).where(Order.id == order_id)
                )

            if customer_id is not None:
                db.execute(
                    delete(Customer).where(
                        Customer.id == customer_id
                    )
                )

            db.commit()