# Step 3 — Publish-Subscribe wiring (order-service → Django webhook)

Depends on: Step 2 (`plans/steps/02-order-service-http-layer.md`) done and verified.
See `plans/00-master-plan.md` for full context.

## Goal

After order-service commits an order creation, publish an event to the monolith so the **existing** webhook dispatch machinery fires — without order-service knowing anything about individual webhook subscribers. This is the Publish-Subscribe pattern from `arquitectura-to-be.md`.

Saleor 2.11 does **not** use Django signals for order events. It uses a `PluginsManager` call-chain: `saleor/order/actions.py::order_created()` (line 37-40) creates an `OrderEvent` audit row **and** calls `get_plugins_manager().order_created(order)`, which fans out to `WebhookPlugin.order_created()` (`saleor/plugins/webhook/plugin.py:32-36`), which enqueues a Celery task (`saleor/plugins/webhook/tasks.py::trigger_webhooks_for_event`). Reuse this chain unchanged — don't touch `actions.py`, `plugins/`, or `webhook/`.

## Files to create/modify

- New: `order_service/app/services/event_publisher.py`
- New: `saleor/order/views.py`
- Modify: `saleor/urls.py` (add one route)
- Modify: `saleor/settings.py` (add `ORDER_SERVICE_SHARED_SECRET`)
- Modify: `order_service/app/services/order_service.py` (call the publisher after a successful create)

## `order_service/app/services/event_publisher.py`

`publish_order_event(event_type: str, order_id: int) -> None` — fire-and-bounded-retry HTTP POST to `DJANGO_EVENTS_URL` (env var, e.g. `http://web:8000/order-service/events/` in compose, `http://localhost:8000/...` locally) with body `{"event_type": event_type, "order_id": order_id}` and header `X-Internal-Token: <ORDER_SERVICE_SHARED_SECRET>`. One retry, short timeout, **must never raise** past this function — log and swallow on final failure, since this is fire-and-forget and must not affect the `POST /orders/` response the client is waiting on.

Wire it into `OrderService.create_order()` (step 1/2's service) — call `publish_order_event("order_created", order.id)` after the repository commit succeeds, before returning.

## `saleor/order/views.py` (new)

```python
@csrf_exempt
def handle_order_service_event(request):
    if request.headers.get("X-Internal-Token") != settings.ORDER_SERVICE_SHARED_SECRET:
        return HttpResponse(status=403)
    payload = json.loads(request.body)
    order = Order.objects.filter(pk=payload["order_id"]).first()
    if order is None:
        return HttpResponse(status=404)
    if payload["event_type"] == "order_created":
        order_created(order=order, user=order.user)  # saleor.order.actions.order_created
    return HttpResponse(status=204)
```
Uses `saleor.order.actions.order_created` (not just `get_plugins_manager().order_created()` directly) specifically to keep the `OrderEvent` audit-log row (`PLACED`) in addition to the webhook dispatch — preserves the dashboard's order timeline.

## `saleor/urls.py`

Add one route next to the existing `plugins/` webhook pattern: `url(r"^order-service/events/$", handle_order_service_event, name="order-service-events")`.

## `saleor/settings.py`

`ORDER_SERVICE_SHARED_SECRET = os.environ.get("ORDER_SERVICE_SHARED_SECRET", "dev-secret-change-me")` — dev-friendly default so existing tests don't break; must be overridden via env in compose/AWS.

## Verification

- Manually: start Django dev server, POST directly to `/order-service/events/` with a real order id (create one via Django admin/shell or step 2's endpoint against the same DB) and the correct shared-secret header — assert 204, assert a new `OrderEvent` row exists, assert (if a `Webhook` row is registered in test/dev settings for `ORDER_CREATED`) a Celery task got enqueued.
- Assert 403 when the header is missing/wrong.
- Assert 404 when `order_id` doesn't exist.
- Unit test `event_publisher.py` with a mocked HTTP call: confirm it retries once then swallows the exception on final failure (never raises).

## Next step

`plans/steps/04-django-http-client.md`
