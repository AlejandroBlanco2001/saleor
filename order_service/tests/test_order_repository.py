"""Integration tests against the real dev Postgres (same DSN Django uses)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService


async def test_create_and_fetch_order_round_trips(session: AsyncSession) -> None:
    repository = OrderRepository(session)
    service = OrderService(repository)

    order = await service.create_order(
        {"language_code": "en", "currency": "USD", "checkout_token": "test-checkout"}
    )

    try:
        assert order.id is not None
        assert order.token

        fetched_by_id = await service.get_order(order.id)
        assert fetched_by_id is not None
        assert fetched_by_id.id == order.id

        fetched_by_token = await repository.get_by_token(order.token)
        assert fetched_by_token is not None
        assert fetched_by_token.id == order.id

        fetched_by_checkout_token = await repository.get_by_checkout_token(
            "test-checkout"
        )
        assert fetched_by_checkout_token is not None
        assert fetched_by_checkout_token.id == order.id
    finally:
        await session.delete(order)
        await session.commit()
