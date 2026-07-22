from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.order_status import OrderStatus


class OrderCreateRequest(BaseModel):
    currency: str
    total_net_amount: Decimal
    total_gross_amount: Decimal
    checkout_token: str

    user_id: int | None = None
    billing_address_id: int | None = None
    shipping_address_id: int | None = None
    user_email: str | None = None
    shipping_method_id: int | None = None
    shipping_method_name: str | None = None
    shipping_price_net_amount: Decimal | None = None
    shipping_price_gross_amount: Decimal | None = None
    voucher_id: int | None = None
    discount_amount: Decimal | None = None
    discount_name: str | None = None
    translated_discount_name: str | None = None
    language_code: str | None = None
    tracking_client_id: str | None = None
    customer_note: str | None = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    checkout_token: str
    status: OrderStatus
    currency: str
    total_net_amount: Decimal
    total_gross_amount: Decimal
    created: datetime

    user_id: int | None
    billing_address_id: int | None
    shipping_address_id: int | None
    shipping_method_id: int | None
    voucher_id: int | None
