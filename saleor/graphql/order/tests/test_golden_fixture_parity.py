"""Golden-fixture parity: proves the Strangler Facade (steps 5/6) returns the
exact same GraphQL shape/values the pre-facade code did.

Golden fixtures (`fixtures/golden_order_*.json`) were captured by running the
same queries, against the same fixture recipes, at commit `c7be1bc8e8`
(the last commit before the query facade landed) via a throwaway `git
worktree` -- see `plans/steps/08-golden-fixture-tests.md` for the exact
capture procedure. `id`/`token`/`created` are normalized to placeholders in
both the golden fixtures and here, since those are inherently per-run.
"""
import json
import os
import time
from unittest import mock

import graphene
import pytest

from ....order.order_service_client import OrderServiceUnavailable
from ...tests.utils import get_graphql_content

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

ORDER_FIELDS = """
    id
    token
    status
    created
    customerNote
    languageCode
    trackingClientId
    discountName
    translatedDiscountName
    displayGrossPrices
    shippingMethodName
    shippingPrice { gross { amount currency } net { amount currency } }
    discount { amount currency }
    total { gross { amount currency } net { amount currency } }
    billingAddress { city countryArea }
    shippingAddress { city countryArea }
    lines { productName quantity }
    weight { value unit }
"""

ORDER_QUERY = f"""
query OrderQuery($id: ID!) {{
    order(id: $id) {{ {ORDER_FIELDS} }}
}}
"""

ORDER_BY_TOKEN_QUERY = f"""
query OrderByToken($token: UUID!) {{
    orderByToken(token: $token) {{ {ORDER_FIELDS} }}
}}
"""


def _load_golden(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


def _normalize(data):
    if data is None:
        return None
    data = dict(data)
    data["id"] = "<ID>"
    data["token"] = "<TOKEN>"
    data["created"] = "<CREATED>"
    return data


def test_order_query_matches_golden_fixture(
    staff_api_client, permission_manage_orders, order_with_lines
):
    order = order_with_lines
    order_id = graphene.Node.to_global_id("Order", order.id)
    staff_api_client.user.user_permissions.add(permission_manage_orders)

    found = get_graphql_content(
        staff_api_client.post_graphql(ORDER_QUERY, {"id": order_id})
    )["data"]["order"]
    missing_id = graphene.Node.to_global_id("Order", order.id + 999999)
    missing = get_graphql_content(
        staff_api_client.post_graphql(ORDER_QUERY, {"id": missing_id})
    )["data"]["order"]

    golden = _load_golden("golden_order_query.json")
    # schema parity: exact same field set, no field silently added/dropped
    assert set(_normalize(found).keys()) == set(golden["found"].keys())
    assert _normalize(found) == golden["found"]
    # business-rule parity: nonexistent id -> null, same as pre-facade
    assert missing == golden["missing"] == None  # noqa: E711


def test_order_by_token_matches_golden_fixture(staff_api_client, order_with_lines):
    order = order_with_lines
    order.status = "unfulfilled"
    order.save()

    found = get_graphql_content(
        staff_api_client.post_graphql(ORDER_BY_TOKEN_QUERY, {"token": str(order.token)})
    )["data"]["orderByToken"]
    missing = get_graphql_content(
        staff_api_client.post_graphql(
            ORDER_BY_TOKEN_QUERY,
            {"token": "11111111-1111-1111-1111-111111111111"},
        )
    )["data"]["orderByToken"]

    golden = _load_golden("golden_order_by_token.json")
    assert set(_normalize(found).keys()) == set(golden["found"].keys())
    assert _normalize(found) == golden["found"]
    assert missing == golden["missing"] == None  # noqa: E711


def test_order_created_via_checkout_matches_golden_fixture(
    checkout_with_item,
    customer_user,
    shipping_method,
    payment_txn_captured,
    staff_api_client,
    permission_manage_orders,
):
    from ....checkout.complete_checkout import _create_order, _prepare_order_data
    from ....tests.utils import flush_post_commit_hooks

    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.payments.add(payment_txn_captured)
    checkout.tracking_code = "tracking_code"
    checkout.save()

    order_data = _prepare_order_data(
        checkout=checkout, lines=list(checkout), discounts=None,
    )
    order = _create_order(checkout=checkout, order_data=order_data, user=customer_user)
    flush_post_commit_hooks()

    order_id = graphene.Node.to_global_id("Order", order.id)
    staff_api_client.user.user_permissions.add(permission_manage_orders)
    requeried = get_graphql_content(
        staff_api_client.post_graphql(ORDER_QUERY, {"id": order_id})
    )["data"]["order"]

    golden = _load_golden("golden_order_created.json")
    assert set(_normalize(requeried).keys()) == set(golden.keys())
    assert _normalize(requeried) == golden


def test_order_query_service_unavailable_is_controlled_and_bounded(
    staff_api_client, permission_manage_orders
):
    order_id = graphene.Node.to_global_id("Order", 1)
    staff_api_client.user.user_permissions.add(permission_manage_orders)

    started = time.monotonic()
    with mock.patch(
        "saleor.graphql.order.resolvers.order_service_client.get_order",
        side_effect=OrderServiceUnavailable("boom"),
    ):
        response = staff_api_client.post_graphql(ORDER_QUERY, {"id": order_id})
    elapsed = time.monotonic() - started

    content = response.json()
    assert content["data"]["order"] is None
    assert content["errors"]
    assert elapsed < 5.0


def test_checkout_complete_service_unavailable_is_controlled_and_bounded(
    checkout_with_item, customer_user, shipping_method, payment_txn_captured
):
    from django.core.exceptions import ValidationError

    from ....checkout.complete_checkout import _create_order, _prepare_order_data

    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.payments.add(payment_txn_captured)
    checkout.save()

    order_data = _prepare_order_data(
        checkout=checkout, lines=list(checkout), discounts=None,
    )
    started = time.monotonic()
    with mock.patch(
        "saleor.checkout.complete_checkout.order_service_client.create_order",
        side_effect=OrderServiceUnavailable("boom"),
    ):
        with pytest.raises(ValidationError):
            _create_order(checkout=checkout, order_data=order_data, user=customer_user)
    elapsed = time.monotonic() - started

    assert elapsed < 5.0
