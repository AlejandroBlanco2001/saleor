# Step 1 — order-service domain + DB layer

Depends on: nothing. First step, self-contained.
See `plans/00-master-plan.md` for full context.

## Goal

Build the pure domain logic (State pattern) and the SQLAlchemy async DB layer for `order-service`, with zero HTTP yet. Verify directly against the existing dev Postgres (same DSN Django already uses) before docker-compose exists.

## Files to create

```
order_service/
  app/
    __init__.py
    domain/
      __init__.py
      order_status.py
    models/
      __init__.py
      order.py
    repositories/
      __init__.py
      order_repository.py
    services/
      __init__.py
      order_service.py
    db/
      __init__.py
      base.py
      session.py
    config.py
  tests/
    __init__.py
    conftest.py
    test_order_status.py
    test_order_repository.py
```

## `app/domain/order_status.py` — State pattern

```python
OrderStatus(str, Enum): DRAFT="draft", UNFULFILLED="unfulfilled",
    PARTIALLY_FULFILLED="partially_fulfilled", FULFILLED="fulfilled", CANCELED="canceled"
```
Exact values confirmed from `saleor/order/__init__.py` (note: Django's own `PARTIALLY_FULFILLED` constant is `"partially fulfilled"` with a space in `saleor/order/__init__.py`, but `context/entregas/w7/pre-experimento.md`'s own correction note and code examples use `"partially_fulfilled"` with underscore — **use the underscore form to match the already-agreed pre-experimento.md example code**, and store status strings as returned by order-service consistently; this is a new column value written by order-service, not read from Django's existing rows, so no legacy value collision).

`_VALID_TRANSITIONS` map + `transition_order_status(order, new_status)` + `InvalidTransitionError` — copy the exact table from `context/entregas/w7/pre-experimento.md`'s "Ejemplos de código" section (already vetted design):
```
UNFULFILLED -> {PARTIALLY_FULFILLED, FULFILLED, CANCELED}
PARTIALLY_FULFILLED -> {FULFILLED, CANCELED}
FULFILLED -> {}
CANCELED -> {}
```
Pure Python, zero I/O, zero Django/FastAPI imports.

## `app/models/order.py` — SQLAlchemy mapping

`OrderEntity` mapped to the **existing** `order_order` table (Django `order` app, model `Order`, default table name `app_label_modelname`). Reference: `saleor/order/models.py` (Order class, already read in full — every field, null/default listed there).

Columns to map, with explicit values order-service must supply on INSERT (Django's Python-side defaults do **not** apply to a raw SQL INSERT from a different process — verify each NOT-NULL column has an explicit value or the INSERT will fail):

| Column | Type | Must supply because |
|---|---|---|
| `id` | Integer PK | autoincrement, let Postgres handle |
| `created` | DateTime(tz) | Django default is a Python callable (`now`), not a DB default |
| `status` | String(32) | required |
| `user_id` | Integer, nullable FK | plain id or None |
| `language_code` | String(35) | NOT NULL, no DB default |
| `tracking_client_id` | String(36) | NOT NULL, no DB default — supply `""` |
| `billing_address_id` | Integer, nullable FK | |
| `shipping_address_id` | Integer, nullable FK | |
| `user_email` | String(254) | NOT NULL — supply `""` |
| `currency` | String | NOT NULL, no DB default |
| `shipping_method_id` | Integer, nullable FK | |
| `shipping_method_name` | String(255), nullable | OK as NULL |
| `shipping_price_net_amount` / `shipping_price_gross_amount` | Numeric | NOT NULL — supply `0` if absent |
| `token` | String(36), unique | NOT NULL, no DB default — **generate `str(uuid4())` server-side**, replicating Django's `Order.save()` override |
| `checkout_token` | String(36) | NOT NULL — supply `""` if absent |
| `total_net_amount` / `total_gross_amount` | Numeric | NOT NULL |
| `voucher_id` | Integer, nullable FK | |
| `discount_amount` | Numeric | NOT NULL — supply `0` |
| `discount_name` / `translated_discount_name` | String(255), nullable | OK as NULL |
| `display_gross_prices` | Boolean | NOT NULL — supply `True` |
| `customer_note` | Text | NOT NULL — supply `""` |
| `weight` | Float (django_measurement `MeasurementField(measurement_class="Mass")` stores as a single float column) | NOT NULL — supply `0.0` |
| `private_metadata` / `metadata` | JSONB | NOT NULL — supply `{}` |

`gift_cards` M2M (`order_order_gift_cards`) — **do not touch**, Django still adds gift cards to the order after creation in step 6.

Before finalizing, cross-check exact column names/types by running (against the existing dev Postgres, read-only): `python manage.py sqlmigrate order 0001` or `\d order_order` in `psql`. Don't guess — verify.

## `app/repositories/order_repository.py`

Async SQLAlchemy: `create(data: dict) -> OrderEntity`, `get_by_id(id: int) -> Optional[OrderEntity]`, `get_by_checkout_token(token: str)`, `get_by_token(token: str)`.

## `app/services/order_service.py`

`create_order(payload) -> OrderEntity` (fills in server-side defaults listed above, generates token, calls repository), `get_order(id) -> Optional[OrderEntity]`.

## `app/db/session.py` + `app/config.py`

Async engine/sessionmaker from `ASYNC_DATABASE_URL` env var (format: `postgresql+asyncpg://user:pass@host:port/db` — same credentials as Django's `DATABASE_URL`, just different scheme/driver). `config.py`: pydantic `Settings` reading env vars with sane local-dev defaults (point at `localhost:5432` matching Django's own default DSN in `saleor/settings.py`).

## Verification

- `pytest order_service/tests/test_order_status.py` — every valid transition succeeds, every invalid one raises `InvalidTransitionError`, `FULFILLED`/`CANCELED` have zero valid outgoing transitions. No DB, no HTTP.
- `pytest order_service/tests/test_order_repository.py` — against the real dev Postgres (reuse the same DB Django points at locally): insert a row via the repository, fetch it back, assert no NOT-NULL violation.
- Cross-check: after inserting via the repository, open `python manage.py shell` in the Django app and confirm `Order.objects.get(pk=<inserted-id>)` loads without error — proves schema compatibility.

## Next step

`plans/steps/02-order-service-http-layer.md`
