from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from src.api.main import app
from src.db.database import SessionLocal, engine
from src.db.models import Customer, Order


def test_demo_orders_list_returns_database_orders():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex
    order_number = f"ORD-{uuid4().int % 10**18:018d}"

    customer_id = None
    order_id = None

    try:
        with SessionLocal() as db:
            assert (
                db.scalar(text("SELECT current_database()"))
                == "resolveai_test"
            )

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
            item
            for item in data
            if item["order_number"] == order_number
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
                db.execute(
                    delete(Order).where(Order.id == order_id)
                )

                db.execute(
                    delete(Customer).where(Customer.id == customer_id)
                )

                db.commit()