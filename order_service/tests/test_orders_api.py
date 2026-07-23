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


async def test_create_order_rejects_net_greater_than_gross(client: AsyncClient) -> None:
    response = await client.post(
        "/orders/",
        json={
            "currency": "USD",
            "total_net_amount": "12.00",
            "total_gross_amount": "10.00",
            "checkout_token": "api-test-bad-totals",
        },
    )

    assert response.status_code == 422


async def test_create_order_rejects_negative_total(client: AsyncClient) -> None:
    response = await client.post(
        "/orders/",
        json={
            "currency": "USD",
            "total_net_amount": "-1.00",
            "total_gross_amount": "10.00",
            "checkout_token": "api-test-negative-total",
        },
    )

    assert response.status_code == 422


async def test_update_status_valid_transition(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/orders/",
            json={
                "currency": "USD",
                "total_net_amount": "10.00",
                "total_gross_amount": "12.00",
                "checkout_token": "api-test-status-valid",
            },
        )
    ).json()
    assert created["status"] == "unfulfilled"

    response = await client.patch(
        f"/orders/{created['id']}/status", json={"status": "fulfilled"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "fulfilled"


async def test_update_status_invalid_transition_rejected_with_422(
    client: AsyncClient,
) -> None:
    created = (
        await client.post(
            "/orders/",
            json={
                "currency": "USD",
                "total_net_amount": "10.00",
                "total_gross_amount": "12.00",
                "checkout_token": "api-test-status-invalid",
            },
        )
    ).json()
    await client.patch(f"/orders/{created['id']}/status", json={"status": "canceled"})

    # canceled -> fulfilled is not a valid transition (terminal state)
    response = await client.patch(
        f"/orders/{created['id']}/status", json={"status": "fulfilled"}
    )

    assert response.status_code == 422


async def test_update_status_missing_order_returns_404(client: AsyncClient) -> None:
    response = await client.patch("/orders/0/status", json={"status": "fulfilled"})

    assert response.status_code == 404
