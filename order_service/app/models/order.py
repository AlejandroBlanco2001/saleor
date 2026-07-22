"""SQLAlchemy mapping onto the existing Django-managed `order_order` table.

No migration: same physical table Django's `saleor.order.models.Order` uses.
Columns not needed by ORD-01/ORD-02 (addresses beyond the FK id, shipping
price, discounts, weight, metadata, etc.) are still mapped because Postgres
requires an explicit value for every NOT NULL column on INSERT — Django's
Python-side field defaults don't apply to an INSERT from this process.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.order_status import OrderStatus

# Django's `status` column is a plain varchar storing the enum *value*
# ("unfulfilled"), not the member name. SQLAlchemy's Enum type defaults to
# storing the name, so it must be told to use values explicitly.
_StatusType = SAEnum(
    OrderStatus,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    native_enum=False,
    length=32,
)


class OrderEntity(Base):
    __tablename__ = "order_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[OrderStatus] = mapped_column(
        _StatusType, default=OrderStatus.UNFULFILLED
    )
    user_id: Mapped[int | None] = mapped_column(default=None)
    language_code: Mapped[str]
    tracking_client_id: Mapped[str] = mapped_column(default="")
    billing_address_id: Mapped[int | None] = mapped_column(default=None)
    shipping_address_id: Mapped[int | None] = mapped_column(default=None)
    user_email: Mapped[str] = mapped_column(default="")
    currency: Mapped[str]
    shipping_method_id: Mapped[int | None] = mapped_column(default=None)
    shipping_method_name: Mapped[str | None] = mapped_column(default=None)
    shipping_price_net_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal(0)
    )
    shipping_price_gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal(0)
    )
    token: Mapped[str] = mapped_column(unique=True)
    checkout_token: Mapped[str] = mapped_column(default="")
    total_net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0))
    total_gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal(0)
    )
    voucher_id: Mapped[int | None] = mapped_column(default=None)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0))
    discount_name: Mapped[str | None] = mapped_column(default=None)
    translated_discount_name: Mapped[str | None] = mapped_column(default=None)
    display_gross_prices: Mapped[bool] = mapped_column(default=True)
    customer_note: Mapped[str] = mapped_column(default="")
    weight: Mapped[float] = mapped_column(default=0.0)
    private_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
