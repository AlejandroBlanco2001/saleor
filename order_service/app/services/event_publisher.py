"""Publish-Subscribe: notify Django of an order-service event.

Fire-and-forget from the caller's perspective: bounded retry, short timeout,
never raises past `publish_order_event` — a notification failure must not
affect the response the `POST /orders/` client is waiting on.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 2.0
_MAX_ATTEMPTS = 2


async def publish_order_event(event_type: str, order_id: int) -> None:
    payload = {"event_type": event_type, "order_id": order_id}
    headers = {"X-Internal-Token": settings.order_service_shared_secret}

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    settings.django_events_url, json=payload, headers=headers
                )
                response.raise_for_status()
            return
        except httpx.HTTPError:
            if attempt == _MAX_ATTEMPTS:
                logger.warning(
                    "Failed to publish %s for order %s after %d attempts",
                    event_type,
                    order_id,
                    _MAX_ATTEMPTS,
                    exc_info=True,
                )
