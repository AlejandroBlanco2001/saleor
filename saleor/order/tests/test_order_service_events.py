import json
from unittest import mock

import pytest
from django.test import override_settings

from ..models import Order, OrderEvent

URL = "/order-service/events/"
SECRET = "test-shared-secret"


@pytest.fixture
def guest_order(customer_user):
    """An order with no linked user, like a guest checkout."""
    address = customer_user.default_billing_address.get_copy()
    return Order.objects.create(
        billing_address=address,
        shipping_address=address,
        user_email="guest@example.com",
        user=None,
    )


@override_settings(ORDER_SERVICE_SHARED_SECRET=SECRET)
def test_missing_header_returns_403(client, order):
    response = client.post(
        URL,
        data=json.dumps({"event_type": "order_created", "order_id": order.pk}),
        content_type="application/json",
    )

    assert response.status_code == 403


@override_settings(ORDER_SERVICE_SHARED_SECRET=SECRET)
def test_wrong_header_returns_403(client, order):
    response = client.post(
        URL,
        data=json.dumps({"event_type": "order_created", "order_id": order.pk}),
        content_type="application/json",
        HTTP_X_INTERNAL_TOKEN="wrong",
    )

    assert response.status_code == 403


@override_settings(ORDER_SERVICE_SHARED_SECRET=SECRET)
def test_missing_order_returns_404(client):
    response = client.post(
        URL,
        data=json.dumps({"event_type": "order_created", "order_id": 0}),
        content_type="application/json",
        HTTP_X_INTERNAL_TOKEN=SECRET,
    )

    assert response.status_code == 404


@override_settings(ORDER_SERVICE_SHARED_SECRET=SECRET)
@mock.patch("saleor.plugins.webhook.plugin.trigger_webhooks_for_event.delay")
def test_order_created_event_happy_path(mock_trigger, client, order, webhook, settings):
    settings.PLUGINS = ["saleor.plugins.webhook.plugin.WebhookPlugin"]

    response = client.post(
        URL,
        data=json.dumps({"event_type": "order_created", "order_id": order.pk}),
        content_type="application/json",
        HTTP_X_INTERNAL_TOKEN=SECRET,
    )

    assert response.status_code == 204
    assert OrderEvent.objects.filter(order=order, type="placed").exists()
    assert mock_trigger.called


@override_settings(ORDER_SERVICE_SHARED_SECRET=SECRET)
@mock.patch("saleor.plugins.webhook.plugin.trigger_webhooks_for_event.delay")
def test_order_created_event_guest_order_does_not_crash(
    mock_trigger, client, guest_order, webhook, settings
):
    """Order.user is a nullable FK; must not be passed as bare None downstream."""
    settings.PLUGINS = ["saleor.plugins.webhook.plugin.WebhookPlugin"]
    assert guest_order.user is None

    response = client.post(
        URL,
        data=json.dumps({"event_type": "order_created", "order_id": guest_order.pk}),
        content_type="application/json",
        HTTP_X_INTERNAL_TOKEN=SECRET,
    )

    assert response.status_code == 204
    assert OrderEvent.objects.filter(order=guest_order, type="placed").exists()


@override_settings(ORDER_SERVICE_SHARED_SECRET=SECRET)
def test_unknown_event_type_still_returns_204_without_side_effects(client, order):
    response = client.post(
        URL,
        data=json.dumps({"event_type": "something_else", "order_id": order.pk}),
        content_type="application/json",
        HTTP_X_INTERNAL_TOKEN=SECRET,
    )

    assert response.status_code == 204
    assert not OrderEvent.objects.filter(order=order).exists()
