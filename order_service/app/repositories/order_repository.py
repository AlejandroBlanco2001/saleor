from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import OrderEntity


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict[str, Any]) -> OrderEntity:
        order = OrderEntity(**data)
        self._session.add(order)
        await self._session.commit()
        await self._session.refresh(order)
        return order

    async def get_by_id(self, order_id: int) -> OrderEntity | None:
        return await self._session.get(OrderEntity, order_id)

    async def get_by_checkout_token(self, token: str) -> OrderEntity | None:
        stmt = select(OrderEntity).where(OrderEntity.checkout_token == token)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_token(self, token: str) -> OrderEntity | None:
        stmt = select(OrderEntity).where(OrderEntity.token == token)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def save(self, order: OrderEntity) -> OrderEntity:
        await self._session.commit()
        await self._session.refresh(order)
        return order
