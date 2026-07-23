import json

import httpx
import respx

from app.config import settings
from app.services.event_publisher import publish_order_event


@respx.mock
async def test_publish_order_event_success_sends_expected_payload() -> None:
    route = respx.post(settings.django_events_url).mock(
        return_value=httpx.Response(204)
    )

    await publish_order_event("order_created", 42)

    assert route.called
    request = route.calls.last.request
    assert request.headers["X-Internal-Token"] == settings.order_service_shared_secret
    assert json.loads(request.content) == {"event_type": "order_created", "order_id": 42}


@respx.mock
async def test_publish_order_event_retries_once_then_swallows() -> None:
    route = respx.post(settings.django_events_url).mock(
        side_effect=httpx.ConnectError("boom")
    )

    await publish_order_event("order_created", 42)  # must not raise

    assert route.call_count == 2


@respx.mock
async def test_publish_order_event_swallows_http_error_status() -> None:
    route = respx.post(settings.django_events_url).mock(
        return_value=httpx.Response(500)
    )

    await publish_order_event("order_created", 42)  # must not raise

    assert route.call_count == 2
