from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.order_status import OrderStatus


class OrderCreateRequest(BaseModel):
    """Totals are computed by Django (tax/discount/shipping pricing stays in
    the monolith -- not yet migrated) and trusted as input here. This is a
    consistency check on what Django sends, not an independent recompute.
    """

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

    @model_validator(mode="after")
    def _check_totals_consistent(self) -> "OrderCreateRequest":
        if self.total_net_amount < 0 or self.total_gross_amount < 0:
            raise ValueError("Order totals must not be negative.")
        if self.total_net_amount > self.total_gross_amount:
            raise ValueError("total_net_amount must not exceed total_gross_amount.")
        if self.shipping_price_net_amount is not None:
            if self.shipping_price_net_amount < 0:
                raise ValueError("shipping_price_net_amount must not be negative.")
            if self.shipping_price_gross_amount is None or (
                self.shipping_price_net_amount > self.shipping_price_gross_amount
            ):
                raise ValueError(
                    "shipping_price_net_amount must not exceed "
                    "shipping_price_gross_amount."
                )
        return self


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus


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
    shipping_method_name: str | None
    shipping_price_net_amount: Decimal
    shipping_price_gross_amount: Decimal
    voucher_id: int | None
    discount_amount: Decimal
    discount_name: str | None
    translated_discount_name: str | None
    display_gross_prices: bool
    customer_note: str
    weight: float
    language_code: str
    tracking_client_id: str
