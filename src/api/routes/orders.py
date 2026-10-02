from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.schemas.order import (
    OrderLookupResponse,
)
from src.tools.order_lookup import (
    get_order,
)


router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


DatabaseDependency = Annotated[
    Session,
    Depends(get_db),
]


@router.get(
    "/{order_number}",
    response_model=OrderLookupResponse,
)
def lookup_order(
    order_number: str,
    db: DatabaseDependency,
) -> OrderLookupResponse:

    result = get_order(
        db,
        order_number,
    )

    return OrderLookupResponse(
        found=result.found,
        order_number=(
            result.order_number
        ),
        customer_name=(
            result.customer_name
        ),
        status=result.status,
        payment_status=(
            result.payment_status
        ),
        total_amount=(
            result.total_amount
        ),
        currency=result.currency,
        carrier=result.carrier,
        tracking_number=(
            result.tracking_number
        ),
        estimated_delivery=(
            result.estimated_delivery
        ),
    )