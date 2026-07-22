from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.order_status import OrderStatus
from app.models.order import OrderEntity
from app.repositories.order_repository import OrderRepository

_SERVER_DEFAULTS: dict[str, Any] = {
    "status": OrderStatus.UNFULFILLED,
    "tracking_client_id": "",
    "user_email": "",
    "shipping_price_net_amount": 0,
    "shipping_price_gross_amount": 0,
    "checkout_token": "",
    "total_net_amount": 0,
    "total_gross_amount": 0,
    "discount_amount": 0,
    "display_gross_prices": True,
    "customer_note": "",
    "weight": 0.0,
    "private_metadata": {},
    "metadata_": {},
}


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def create_order(self, payload: dict[str, Any]) -> OrderEntity:
        data = {
            **_SERVER_DEFAULTS,
            **payload,
            "created": datetime.now(UTC),
            "token": str(uuid4()),
        }
        return await self._repository.create(data)

    async def get_order(self, order_id: int) -> OrderEntity | None:
        return await self._repository.get_by_id(order_id)
