# Step 7 — docker-compose.yml + order_service/Dockerfile

Depends on: Steps 1-6 done and verified locally/standalone.
See `plans/00-master-plan.md` for full context.

No `docker-compose.yml` exists in the repo today (confirmed) — creating one does not violate `CLAUD.md`'s "do NOT modify docker-compose.yml" rule (nothing to modify).

## Files to create

- `docker-compose.yml` (repo root)
- `order_service/Dockerfile`
- `order_service/requirements.txt`

## `docker-compose.yml` services

- `db`: `postgres:12` (or a version matching `psycopg2-binary` compatibility already pinned in `requirements.txt` — check the pin before choosing), env `POSTGRES_USER=saleor`, `POSTGRES_PASSWORD=saleor`, `POSTGRES_DB=saleor`, named volume for persistence, healthcheck `pg_isready -U saleor`.
- `redis`: `redis:6-alpine`. Check `saleor/settings.py`/`saleor/celeryconf.py` for the exact broker env var name (likely `CELERY_BROKER_URL`) before wiring.
- `web`: `build: { context: ., dockerfile: Dockerfile }`, env `DATABASE_URL=postgres://saleor:saleor@db:5432/saleor`, `ORDER_SERVICE_URL=http://order-service:8000`, `ORDER_SERVICE_SHARED_SECRET=<matches order-service's env>`, `CELERY_BROKER_URL=redis://redis:6379/0` (adjust to actual var name), port `8000:8000`, `depends_on: [db, redis]`. Command: run `python manage.py migrate` then start gunicorn (the `Procfile`'s `web` line: `gunicorn --bind :8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker saleor.asgi:application`) — since compose doesn't auto-run Heroku's `release` step, either chain both in a `command:` override or use an entrypoint script.
- `celeryworker`: same build/env as `web`, `command: celery worker -A saleor.celeryconf:app --loglevel=info -E` (verbatim from `Procfile`), `depends_on: [db, redis]`.
- `order-service`: `build: { context: ., dockerfile: order_service/Dockerfile }`, env `ASYNC_DATABASE_URL=postgresql+asyncpg://saleor:saleor@db:5432/saleor`, `DJANGO_EVENTS_URL=http://web:8000/order-service/events/`, `ORDER_SERVICE_SHARED_SECRET=<same value as web's>`, port `8001:8000` (external 8001 to avoid clashing with `web`'s 8000), `depends_on: [db]`, healthcheck against `GET /health`.

## `order_service/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY order_service/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY order_service/ /app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## `order_service/requirements.txt`

`fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `asyncpg`, `httpx`, `pydantic`, plus dev/test-only (`pytest`, `pytest-asyncio`, and a mock-HTTP library matching whatever step 3/4 picked) — split into `requirements.txt` / `requirements-dev.txt` if the team wants parity with the monolith's convention.

## Verification

- `docker-compose up -d`, wait for healthchecks, then:
  - `docker-compose exec web python manage.py migrate` succeeds (creates/updates the schema `order-service` depends on).
  - `docker-compose exec web python manage.py shell` → confirm `Order.objects.count()` works.
  - Manual GraphQL query (`order(id: ...)`) against `http://localhost:8000/graphql/` hits the real `order-service` container (check `order-service`'s logs for the incoming request).
  - Trigger a full checkout-completion flow (existing storefront test flow or a scripted GraphQL mutation sequence) and confirm an order is created via `order-service`, visible both through `GET http://localhost:8001/orders/{id}` and the Django admin/ORM.
  - Re-run the mocked unit tests from steps 4-6 as integration tests against the real containers (point `ORDER_SERVICE_URL` at `http://localhost:8001` from a host-side test run, or run the test suite inside the `web` container).
- Kill the `order-service` container (`docker-compose stop order-service`) mid-flow and confirm the monolith returns a controlled error within the configured timeout — not a hang — for both a query and a checkout-completion attempt.

## Next step

`plans/steps/08-golden-fixture-tests.md`
