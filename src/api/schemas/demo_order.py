from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class DemoOrderResponse(BaseModel):
    id: int
    order_number: str

    customer_id: int
    customer_name: str

    status: str
    payment_status: str

    total_amount: Decimal
    currency: str

    shipping_address: str

    carrier: str | None = None
    tracking_number: str | None = None
    estimated_delivery: date | None = None

    created_at: datetime
    updated_at: datetime