# Step 2 — order-service HTTP layer [DONE]

Depends on: Step 1 (`plans/steps/01-order-service-domain-db.md`) done and verified.
See `plans/00-master-plan.md` for full context.

## Goal

Expose the domain/DB layer from step 1 as a FastAPI app: `POST /orders/`, `GET /orders/{id}`, `GET /orders/by-token/{token}`, `GET /health`. In-process tests only — no docker-compose needed yet.

## Files to create

```
order_service/
  app/
    main.py
    schemas/
      __init__.py
      order.py
    routers/
      __init__.py
      orders.py
      health.py
  tests/
    test_orders_api.py
```

## `app/schemas/order.py` — Pydantic

- `OrderCreateRequest`: mirrors the payload the Django facade will send in step 6 — `user_id`, `billing_address_id`, `shipping_address_id`, `user_email`, `currency`, `shipping_method_id`, `shipping_method_name`, `shipping_price_net_amount`, `shipping_price_gross_amount`, `checkout_token`, `total_net_amount`, `total_gross_amount`, `voucher_id`, `discount_amount`, `discount_name`, `translated_discount_name`, `language_code`, `tracking_client_id`, `customer_note` — all optional except `currency`/`total_net_amount`/`total_gross_amount`/`checkout_token` (order-service supplies defaults for the rest, per step 1's table).
- `OrderResponse`: `id`, `token`, `checkout_token`, `status`, `currency`, `total_net_amount`, `total_gross_amount`, `created`, plus the nullable FK ids (`user_id`, `billing_address_id`, `shipping_address_id`, `shipping_method_id`, `voucher_id`) — the Django facade needs these ids in steps 5/6 to rehydrate an in-memory `Order` whose nested relations still resolve correctly.

## `app/routers/orders.py`

- `POST /orders/` → calls `OrderService.create_order()` from step 1, returns `OrderResponse` (201). This is ORD-01.
- `GET /orders/{id}` → `OrderService.get_order()`, 404 if missing (`OrderResponse | None`). This is ORD-02.
- `GET /orders/by-token/{token}` → same shape via `get_by_token`, needed to back Django's `resolve_order_by_token` facade in step 5.

## `app/routers/health.py`

`GET /health` → `{"status": "ok"}`, no DB touch needed (or a trivial `SELECT 1` if you want it to double as a DB liveness check) — used by docker-compose healthcheck in step 7.

## `app/main.py`

`FastAPI()` instance, include both routers, startup/shutdown hooks to open/close the async engine from step 1's `db/session.py`.

## Verification

- `pytest order_service/tests/test_orders_api.py` using `httpx.AsyncClient(transport=ASGITransport(app=app))`, in-process, against the same dev Postgres from step 1:
  - `POST /orders/` happy path → 201, response has `id`/`token`/`status="unfulfilled"`.
  - `GET /orders/{id}` found → 200, same data.
  - `GET /orders/{id}` missing → 404.
  - `GET /orders/by-token/{token}` found/missing.
- Manually run `uvicorn app.main:app --reload` from `order_service/` and hit it with `curl`/Postman to sanity check before wiring anything else.

## Next step

`plans/steps/03-pubsub-webhook-wiring.md`
