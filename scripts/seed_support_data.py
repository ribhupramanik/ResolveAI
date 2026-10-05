from datetime import (
    date,
    datetime,
    timezone,
)
from decimal import Decimal

from sqlalchemy import select

from src.db.database import SessionLocal
from src.db.models import (
    Customer,
    Order,
    Refund,
)


def ensure_refund_demo(
    db,
    order: Order,
) -> bool:
    existing_refund = db.scalar(
        select(Refund).where(Refund.refund_number == "REF-10003")
    )

    if existing_refund is not None:
        return False

    refund = Refund(
        refund_number="REF-10003",
        order_id=order.id,
        status="processing",
        amount=Decimal("3899.00"),
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

    db.add(refund)

    return True


def main() -> None:
    db = SessionLocal()

    try:
        existing_order = db.scalar(
            select(Order).where(Order.order_number == "ORD-10001")
        )

        if existing_order:
            refund_order = db.scalar(
                select(Order).where(Order.order_number == "ORD-10003")
            )

            if refund_order is None:
                raise RuntimeError(
                    "ORD-10003 is missing from existing support demo data."
                )

            refund_created = ensure_refund_demo(
                db,
                refund_order,
            )

            if refund_created:
                db.commit()
                print("Refund demo data created.")
            else:
                print("Support demo data already exists.")

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
                total_amount=Decimal("2499.00"),
                currency="INR",
                carrier="DemoShip",
                tracking_number=("DSH10001001"),
                estimated_delivery=date(
                    2026,
                    10,
                    4,
                ),
                shipping_address=("12 Park Road, Kolkata, West Bengal"),
            ),
            Order(
                order_number="ORD-10002",
                customer_id=customer_1.id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                carrier=None,
                tracking_number=None,
                estimated_delivery=None,
                shipping_address=("12 Park Road, Kolkata, West Bengal"),
            ),
            Order(
                order_number="ORD-10003",
                customer_id=customer_2.id,
                status="delivered",
                payment_status="paid",
                total_amount=Decimal("3899.00"),
                currency="INR",
                carrier="DemoShip",
                tracking_number=("DSH10003003"),
                estimated_delivery=date(
                    2026,
                    9,
                    25,
                ),
                shipping_address=("41 Lake View, Howrah, West Bengal"),
            ),
        ]

        db.add_all(orders)
        db.flush()

        refund_order = next(
            order for order in orders if order.order_number == "ORD-10003"
        )

        ensure_refund_demo(
            db,
            refund_order,
        )

        db.commit()

        print("Support demo data created.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
