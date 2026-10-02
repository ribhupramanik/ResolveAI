from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OrderLookupResponse(BaseModel):
    found: bool
    order_number: str

    customer_name: str | None = None
    status: str | None = None
    payment_status: str | None = None

    total_amount: Decimal | None = None
    currency: str | None = None

    carrier: str | None = None
    tracking_number: str | None = None

    estimated_delivery: date | None = None