from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


OrderStatus = Literal[
    "processing",
    "shipped",
    "delivered",
    "cancelled",
]

PaymentStatus = Literal[
    "pending",
    "unpaid",
    "paid",
    "failed",
    "refunded",
]


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


class DemoOrderCreate(BaseModel):
    order_number: str = Field(
        min_length=5,
        max_length=30,
        pattern=r"^ORD-[0-9]+$",
    )

    customer_id: int = Field(gt=0)

    status: OrderStatus

    payment_status: PaymentStatus

    total_amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )

    shipping_address: str = Field(min_length=1)

    carrier: str | None = Field(
        default=None,
        max_length=100,
    )

    tracking_number: str | None = Field(
        default=None,
        max_length=100,
    )

    estimated_delivery: date | None = None
