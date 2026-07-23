# Step 4 — Django → order-service HTTP client [DONE]

Depends on: Step 2 (`plans/steps/02-order-service-http-layer.md`) done. Independent of step 3.
See `plans/00-master-plan.md` for full context.

## Goal

Build the resilience infrastructure (timeout + one bounded retry) the two Strangler Facade seams (steps 5 and 6) will both use. This is pure Django-side infra, no facade edits yet — testable standalone against a mock HTTP server.

`requests` is already a pinned dependency (`requirements.txt`) — no new package needed on the Django side. `urllib3` (a `requests` dependency) already ships `Retry`/`HTTPAdapter`.

## Files to create/modify

- New: `saleor/order/order_service_client.py`
- Modify: `saleor/settings.py` (new `ORDER_SERVICE_*` settings)

## `saleor/order/order_service_client.py`

```python
class OrderServiceUnavailable(Exception):
    pass

_session = requests.Session()
_retry = Retry(total=1, connect=1, read=1, status_forcelist=[502, 503, 504], backoff_factor=0.1)
_session.mount("http://", HTTPAdapter(max_retries=_retry))
_session.mount("https://", HTTPAdapter(max_retries=_retry))

def create_order(payload: dict) -> dict:
    try:
        resp = _session.post(f"{settings.ORDER_SERVICE_URL}/orders/", json=payload,
                              timeout=(settings.ORDER_SERVICE_TIMEOUT_CONNECT, settings.ORDER_SERVICE_TIMEOUT_READ))
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        raise OrderServiceUnavailable(str(exc)) from exc

def get_order(order_id: int) -> Optional[dict]:
    # same pattern, GET /orders/{id}, return None on 404, raise OrderServiceUnavailable on timeout/5xx

def get_order_by_token(token: str) -> Optional[dict]:
    # same pattern, GET /orders/by-token/{token}
```

Key behavior to get right:
- `Retry(total=1, ...)` gives exactly one bounded retry on connection errors and the listed 5xx codes — matches the "timeout corto + reintento acotado" requirement, not unbounded retries.
- Short `(connect, read)` timeout tuple — short enough that a hung order-service surfaces as a controlled failure quickly, not a multi-second hang.
- A clean 404 from order-service returns `None`, not an exception — callers (steps 5/6) treat `None` as "order not found" (valid GraphQL null / 404 checkout case), while `OrderServiceUnavailable` means "service is down/slow" and gets a different, more alarming error message upstream.

## `saleor/settings.py`

```python
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8001")
ORDER_SERVICE_TIMEOUT_CONNECT = float(os.environ.get("ORDER_SERVICE_TIMEOUT_CONNECT", "0.5"))
ORDER_SERVICE_TIMEOUT_READ = float(os.environ.get("ORDER_SERVICE_TIMEOUT_READ", "2.0"))
```
Defaults are dev-friendly so existing test runs don't need new env vars set.

## Verification

Unit test (e.g. `saleor/order/tests/test_order_service_client.py`) against a mock HTTP server (`pytest-httpserver` or `responses` library — check what's already available in `requirements_dev.txt` before adding a new test dependency):
- Happy path: 201/200 → parsed dict returned.
- 404 on GET → `None` returned, no exception.
- Connection refused / timeout → `OrderServiceUnavailable` raised, and the mock server/mock adapter shows exactly 2 attempts total (1 original + 1 retry), not more.
- 500 with retry exhausted → `OrderServiceUnavailable` raised.

## Next step

`plans/steps/05-query-facade.md`
