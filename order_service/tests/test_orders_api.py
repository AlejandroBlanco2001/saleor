from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_create_order_happy_path(client: AsyncClient) -> None:
    response = await client.post(
        "/orders/",
        json={
            "currency": "USD",
            "total_net_amount": "10.00",
            "total_gross_amount": "12.00",
            "checkout_token": "api-test-create",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "unfulfilled"
    assert body["id"] is not None
    assert body["token"]

    delete_response = await client.get(f"/orders/{body['id']}")
    assert delete_response.status_code == 200


async def test_get_order_by_id_found(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/orders/",
            json={
                "currency": "USD",
                "total_net_amount": "10.00",
                "total_gross_amount": "12.00",
                "checkout_token": "api-test-get-by-id",
            },
        )
    ).json()

    response = await client.get(f"/orders/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_order_by_id_missing(client: AsyncClient) -> None:
    response = await client.get("/orders/0")

    assert response.status_code == 404


async def test_get_order_by_token_found(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/orders/",
            json={
                "currency": "USD",
                "total_net_amount": "10.00",
                "total_gross_amount": "12.00",
                "checkout_token": "api-test-get-by-token",
            },
        )
    ).json()

    response = await client.get(f"/orders/by-token/{created['token']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_order_by_token_missing(client: AsyncClient) -> None:
    response = await client.get("/orders/by-token/does-not-exist")

    assert response.status_code == 404
