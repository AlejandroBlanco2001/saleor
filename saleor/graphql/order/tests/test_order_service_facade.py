"""Verifies the Strangler Facade in `saleor/graphql/order/resolvers.py`:
`order`/`orderByToken` fetch the root Order from order-service (mocked here,
network layer already covered by `saleor/order/tests/test_order_service_client.py`)
while nested fields keep resolving off the hydrated in-memory instance.
"""
from unittest import mock

import graphene

from ....order.order_service_client import OrderServiceUnavailable
from ...tests.utils import get_graphql_content

ORDER_QUERY = """
query OrderQuery($id: ID!) {
    order(id: $id) {
        id
        token
        status
        created
        lines {
            id
        }
        events {
            id
        }
    }
}
"""

ORDER_BY_TOKEN_QUERY = """
query OrderByToken($token: UUID!) {
    orderByToken(token: $token) {
        id
        token
        status
    }
}
"""


def _order_service_payload(order_id=1):
    return {
        "id": order_id,
        "token": "11111111-1111-1111-1111-111111111111",
        "checkout_token": "",
        "status": "unfulfilled",
        "currency": "USD",
        "created": "2024-01-01T00:00:00+00:00",
        "total_net_amount": "10.00",
        "total_gross_amount": "12.30",
        "user_id": None,
        "billing_address_id": None,
        "shipping_address_id": None,
        "shipping_method_id": None,
        "shipping_method_name": None,
        "shipping_price_net_amount": "0.00",
        "shipping_price_gross_amount": "0.00",
        "voucher_id": None,
        "discount_amount": "0.00",
        "discount_name": None,
        "translated_discount_name": None,
        "display_gross_prices": True,
        "customer_note": "",
        "weight": 0.0,
        "language_code": "en",
        "tracking_client_id": "",
    }


def test_order_query_found(staff_api_client, permission_manage_orders):
    order_id = graphene.Node.to_global_id("Order", 1)
    with mock.patch(
        "saleor.graphql.order.resolvers.order_service_client.get_order",
        return_value=_order_service_payload(),
    ):
        staff_api_client.user.user_permissions.add(permission_manage_orders)
        response = staff_api_client.post_graphql(ORDER_QUERY, {"id": order_id})

    content = get_graphql_content(response)
    data = content["data"]["order"]
    assert data["id"] == order_id
    assert data["status"] == "UNFULFILLED"
    assert data["lines"] == []
    assert data["events"] == []


def test_order_query_missing_returns_null(staff_api_client, permission_manage_orders):
    order_id = graphene.Node.to_global_id("Order", 999)
    with mock.patch(
        "saleor.graphql.order.resolvers.order_service_client.get_order",
        return_value=None,
    ):
        staff_api_client.user.user_permissions.add(permission_manage_orders)
        response = staff_api_client.post_graphql(ORDER_QUERY, {"id": order_id})

    content = get_graphql_content(response)
    assert content["data"]["order"] is None


def test_order_query_service_unavailable_returns_error_quickly(
    staff_api_client, permission_manage_orders
):
    order_id = graphene.Node.to_global_id("Order", 1)
    with mock.patch(
        "saleor.graphql.order.resolvers.order_service_client.get_order",
        side_effect=OrderServiceUnavailable("boom"),
    ):
        staff_api_client.user.user_permissions.add(permission_manage_orders)
        response = staff_api_client.post_graphql(ORDER_QUERY, {"id": order_id})

    content = response.json()
    assert content["data"]["order"] is None
    assert content["errors"]


def test_order_by_token_found(staff_api_client):
    payload = _order_service_payload()
    with mock.patch(
        "saleor.graphql.order.resolvers.order_service_client.get_order_by_token",
        return_value=payload,
    ):
        response = staff_api_client.post_graphql(
            ORDER_BY_TOKEN_QUERY, {"token": payload["token"]}
        )

    content = get_graphql_content(response)
    assert content["data"]["orderByToken"]["token"] == payload["token"]


def test_order_by_token_missing_returns_null(staff_api_client):
    with mock.patch(
        "saleor.graphql.order.resolvers.order_service_client.get_order_by_token",
        return_value=None,
    ):
        response = staff_api_client.post_graphql(
            ORDER_BY_TOKEN_QUERY, {"token": "11111111-1111-1111-1111-111111111111"}
        )

    content = get_graphql_content(response)
    assert content["data"]["orderByToken"] is None
