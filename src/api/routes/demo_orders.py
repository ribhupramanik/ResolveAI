from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.schemas.demo_order import (
    DemoOrderCreate,
    DemoOrderResponse,
    DemoOrderUpdate,
)
from src.db.models import (
    ActionExecutionAudit,
    Customer,
    Order,
    PendingAction,
    Refund,
)

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
            is_demo_managed=order.is_demo_managed,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
        for order, customer_name in rows
    ]


@router.post(
    "",
    response_model=DemoOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_demo_order(
    payload: DemoOrderCreate,
    db: DatabaseDependency,
) -> DemoOrderResponse:

    existing_order = db.scalar(
        select(Order.id).where(Order.order_number == payload.order_number)
    )

    if existing_order is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order number already exists.",
        )

    customer = None

    if payload.customer_id is not None:
        customer = db.get(
            Customer,
            payload.customer_id,
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )

    try:
        if customer is None:
            token = uuid4().hex

            customer = Customer(
                customer_code=f"DEMO-{token[:12].upper()}",
                name=f"Demo Customer {token[:8].upper()}",
                email=f"demo-{token}@example.invalid",
            )

            db.add(customer)
            db.flush()

        order_data = payload.model_dump(exclude={"customer_id"})

        order = Order(
            **order_data,
            customer_id=customer.id,
            is_demo_managed=True,
        )

        db.add(order)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order or customer already exists.",
        ) from exc

    db.refresh(order)

    return DemoOrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_name=customer.name,
        is_demo_managed=order.is_demo_managed,
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


@router.patch(
    "/{order_id}",
    response_model=DemoOrderResponse,
)
def update_demo_order(
    order_id: int,
    payload: DemoOrderUpdate,
    db: DatabaseDependency,
) -> DemoOrderResponse:

    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    existing_action = db.scalar(
        select(PendingAction.id)
        .where(
            PendingAction.target_type == "order",
            PendingAction.target_identifier == order.order_number,
            PendingAction.status.in_(("pending", "confirmed", "executed")),
        )
        .limit(1)
    )

    if existing_action is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This order has an active or executed action "
                "and cannot be modified through the demo manager."
            ),
        )

    existing_refund = db.scalar(
        select(Refund.id).where(Refund.order_id == order.id).limit(1)
    )

    if existing_refund is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This order has refund history "
                "and cannot be modified through the demo manager."
            ),
        )

    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(order, field, value)

    db.commit()
    db.refresh(order)

    return DemoOrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_name=order.customer.name,
        status=order.status,
        payment_status=order.payment_status,
        total_amount=order.total_amount,
        currency=order.currency,
        shipping_address=order.shipping_address,
        carrier=order.carrier,
        tracking_number=order.tracking_number,
        estimated_delivery=order.estimated_delivery,
        is_demo_managed=order.is_demo_managed,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_demo_order(
    order_id: int,
    db: DatabaseDependency,
) -> None:

    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    if not order.is_demo_managed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only demo-managed orders can be deleted.",
        )

    existing_action = db.scalar(
        select(PendingAction.id)
        .where(
            PendingAction.target_type == "order",
            PendingAction.target_identifier == order.order_number,
        )
        .limit(1)
    )

    if existing_action is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This order has action history and cannot be deleted."),
        )

    existing_audit = db.scalar(
        select(ActionExecutionAudit.id)
        .where(
            ActionExecutionAudit.target_type == "order",
            ActionExecutionAudit.target_identifier == order.order_number,
        )
        .limit(1)
    )

    if existing_audit is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This order has execution audit history and cannot be deleted."),
        )

    existing_refund = db.scalar(
        select(Refund.id).where(Refund.order_id == order.id).limit(1)
    )

    if existing_refund is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This order has refund history and cannot be deleted."),
        )

    try:
        db.delete(order)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This order has related records and cannot be deleted."),
        ) from exc
