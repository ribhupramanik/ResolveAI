from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.schemas.demo_order import DemoOrderResponse
from src.db.models import Customer, Order


router = APIRouter(
    prefix="/demo/orders",
    tags=["Demo Orders"],
)


DatabaseDependency = Annotated[
    Session,
    Depends(get_db),
]


@router.get(
    "",
    response_model=list[DemoOrderResponse],
)
def list_demo_orders(
    db: DatabaseDependency,
) -> list[DemoOrderResponse]:

    statement = (
        select(
            Order,
            Customer.name,
        )
        .join(
            Customer,
            Order.customer_id == Customer.id,
        )
        .order_by(Order.id.desc())
    )

    rows = db.execute(statement).all()

    return [
        DemoOrderResponse(
            id=order.id,
            order_number=order.order_number,
            customer_id=order.customer_id,
            customer_name=customer_name,
            status=order.status,
            payment_status=order.payment_status,
            total_amount=order.total_amount,
            currency=order.currency,
            shipping_address=order.shipping_address,
            carrier=order.carrier,
            tracking_number=order.tracking_number,
            estimated_delivery=order.estimated_delivery,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
        for order, customer_name in rows
    ]