from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.db.database import SessionLocal
from src.db.models import (
    Customer,
    Order,
)


def main() -> None:
    db = SessionLocal()

    try:
        existing_order = db.scalar(
            select(Order).where(
                Order.order_number
                == "ORD-10001"
            )
        )

        if existing_order:
            print(
                "Support demo data "
                "already exists."
            )
            return

        customer_1 = Customer(
            customer_code="CUST-1001",
            name="Aarav Sharma",
            email="aarav@example.com",
        )

        customer_2 = Customer(
            customer_code="CUST-1002",
            name="Meera Sen",
            email="meera@example.com",
        )

        db.add_all(
            [
                customer_1,
                customer_2,
            ]
        )

        db.flush()

        orders = [
            Order(
                order_number="ORD-10001",
                customer_id=customer_1.id,
                status="shipped",
                payment_status="paid",
                total_amount=Decimal(
                    "2499.00"
                ),
                currency="INR",
                carrier="DemoShip",
                tracking_number=(
                    "DSH10001001"
                ),
                estimated_delivery=date(
                    2026,
                    10,
                    4,
                ),
                shipping_address=(
                    "12 Park Road, "
                    "Kolkata, West Bengal"
                ),
            ),
            Order(
                order_number="ORD-10002",
                customer_id=customer_1.id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal(
                    "1299.00"
                ),
                currency="INR",
                carrier=None,
                tracking_number=None,
                estimated_delivery=None,
                shipping_address=(
                    "12 Park Road, "
                    "Kolkata, West Bengal"
                ),
            ),
            Order(
                order_number="ORD-10003",
                customer_id=customer_2.id,
                status="delivered",
                payment_status="paid",
                total_amount=Decimal(
                    "3899.00"
                ),
                currency="INR",
                carrier="DemoShip",
                tracking_number=(
                    "DSH10003003"
                ),
                estimated_delivery=date(
                    2026,
                    9,
                    25,
                ),
                shipping_address=(
                    "41 Lake View, "
                    "Howrah, West Bengal"
                ),
            ),
        ]

        db.add_all(orders)

        db.commit()

        print(
            "Support demo data created."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()