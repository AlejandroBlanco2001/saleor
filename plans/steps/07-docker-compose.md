# Step 7 — docker-compose.yml + order_service/Dockerfile (local, and local-against-cloud)

Depends on: Steps 1-6 done and verified locally/standalone.
See `plans/00-master-plan.md` for full context, especially "Revised target deployment".

No `docker-compose.yml` exists in the repo today (confirmed) — creating one does not violate `CLAUD.md`'s "do NOT modify docker-compose.yml" rule (nothing to modify).

## Goal

One `docker-compose.yml`, three run modes via Compose **profiles**, so the same file serves both a fully-local dev loop and "monolith on my machine, everything else in AWS":

1. **`local`** — full stack (`db`, `redis`, `web`, `celeryworker`, `order-service`), nothing touches AWS. Default for day-to-day dev and for steps 1-8's integration tests.
2. **`monolith`** — only `web` + `celeryworker` run here; `DATABASE_URL`/`CELERY_BROKER_URL`/`ORDER_SERVICE_URL` point at AWS (RDS/SQS/the order-service EC2 instance from step 9).
3. **`order-service`** — only the `order-service` container runs here; `ASYNC_DATABASE_URL` points at RDS, `DJANGO_EVENTS_URL` points at wherever the monolith is currently reachable from (see caveat below — this is the one mode without a clean answer).

## Files to create

- `docker-compose.yml` (repo root)
- `order_service/Dockerfile`
- `order_service/requirements.txt` (mirrors `order_service/pyproject.toml`'s deps — the uv project stays the source of truth for local dev/tests, this file is only for the Docker build)
- `.env.local.example` (all vars for the `local` profile, safe placeholder values, committed)
- `.env.cloud.example` (all vars for `monolith`/`order-service` profiles — RDS endpoint, SQS URL, shared secret placeholders, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` if not using an instance/local profile credential chain — committed as a template; the real `.env.cloud` is gitignored)

## `docker-compose.yml` shape

```yaml
services:
  db:
    image: postgres:12
    profiles: ["local"]
    environment:
      POSTGRES_USER: saleor
      POSTGRES_PASSWORD: saleor
      POSTGRES_DB: saleor
    volumes: ["saleor-db:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U saleor"]

  redis:
    image: redis:6-alpine
    profiles: ["local"]

  web:
    build: { context: ., dockerfile: Dockerfile }
    profiles: ["local", "monolith"]
    env_file: ${ENV_FILE:-.env.local}
    ports: ["8000:8000"]
    depends_on: []   # `local` profile adds db/redis deps via override below, `monolith` has none (AWS-hosted)
    command: ["sh", "-c", "python manage.py migrate && gunicorn --bind :8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker saleor.asgi:application"]

  celeryworker:
    build: { context: ., dockerfile: Dockerfile }
    profiles: ["local", "monolith"]
    env_file: ${ENV_FILE:-.env.local}
    command: ["celery", "worker", "-A", "saleor.celeryconf:app", "--loglevel=info", "-E"]

  order-service:
    build: { context: ., dockerfile: order_service/Dockerfile }
    profiles: ["local", "order-service"]
    env_file: ${ENV_FILE:-.env.local}
    ports: ["8001:8000"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

volumes:
  saleor-db:
```

Notes:
- `db`/`redis` only ever run under `local` — the `monolith`/`order-service` profiles are explicitly the "these are in AWS now" modes, so there's nothing local to depend on. Don't add `depends_on: [db, redis]` unconditionally to `web`/`celeryworker`/`order-service` — that would force `db`/`redis` up even when running `--profile monolith` alone. If Compose's lack of per-profile `depends_on` becomes annoying, an override file (`docker-compose.local.yml` adding the `depends_on` only, merged via `-f docker-compose.yml -f docker-compose.local.yml` for the `local` profile) is an acceptable escape hatch — don't over-engineer this up front.
- `env_file: ${ENV_FILE:-.env.local}` — `local` runs need no extra flags (`docker compose --profile local up`, reads `.env.local`); cloud-pointed runs export `ENV_FILE=.env.cloud` first (`ENV_FILE=.env.cloud docker compose --profile monolith up`).
- `web`'s command chains `migrate` then `gunicorn` in one line since Compose (unlike Heroku) doesn't run a separate `release` step — same reasoning as the original plan.

## `.env.local.example` (values for the `local` profile)

```
DATABASE_URL=postgres://saleor:saleor@db:5432/saleor
CELERY_BROKER_URL=redis://redis:6379/0
ORDER_SERVICE_URL=http://order-service:8000
ORDER_SERVICE_SHARED_SECRET=dev-secret-change-me
ASYNC_DATABASE_URL=postgresql+asyncpg://saleor:saleor@db:5432/saleor
DJANGO_EVENTS_URL=http://web:8000/order-service/events/
```

## `.env.cloud.example` (values for `monolith` / `order-service` profiles)

```
# monolith profile
DATABASE_URL=postgres://<user>:<password>@<rds-endpoint>:5432/saleor
CELERY_BROKER_URL=sqs://<region>   # credentials via AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY below, or an existing local AWS profile
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
ORDER_SERVICE_URL=http://<order-service-ec2-public-ip>:8000
ORDER_SERVICE_SHARED_SECRET=<matches order-service's>

# order-service profile
ASYNC_DATABASE_URL=postgresql+asyncpg://<user>:<password>@<rds-endpoint>:5432/saleor
DJANGO_EVENTS_URL=http://<wherever-the-monolith-is-reachable>:8000/order-service/events/
```

**Known gap, call it out rather than silently paper over it**: in the `order-service`-only mode, `DJANGO_EVENTS_URL` has no stable target — the monolith is running on a developer's machine, not a fixed cloud address. Acceptable answers, pick one and document it in the README when this mode is actually used: (a) a tunnel (ngrok/Cloudflare Tunnel/SSH reverse tunnel) exposing the local monolith's `/order-service/events/` endpoint, (b) accept that in this mode webhook events are best-effort/lost (the retry-then-swallow behavior in `event_publisher.py` already tolerates this — see `plans/GOTCHAS.md`'s urllib3/retry section for the parallel Django→order-service case), or (c) just don't use this mode for anything that needs the event round-trip; it's mainly useful for order-service's own `pytest order_service/tests/` run against a real RDS instance.

## `order_service/Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY order_service/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY order_service/app /app/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

(Python 3.12, not 3.11 — matches `order_service/pyproject.toml`'s actual pin from step 1, not the master plan's original draft assumption.)

## `order_service/requirements.txt`

Generate from the uv project rather than hand-copying, so it can't drift: `cd order_service && uv export --no-dev --format requirements-txt > requirements.txt` (or `uv pip compile pyproject.toml -o requirements.txt` depending on the installed `uv` version — check `uv export --help` first). Re-run this whenever `order_service/pyproject.toml`'s deps change.

## Verification

- `local` profile: `docker compose --profile local up -d`, wait for healthchecks, then:
  - `docker compose exec web python manage.py migrate` succeeds.
  - `docker compose exec web python manage.py shell` → `Order.objects.count()` works.
  - Manual GraphQL `order(id: ...)` query against `http://localhost:8000/graphql/` hits the real `order-service` container (check its logs).
  - Full checkout-completion flow creates an order via `order-service`, visible through `GET http://localhost:8001/orders/{id}` and the Django admin/ORM.
  - `docker compose stop order-service` mid-flow → monolith returns a controlled error within the configured timeout for both a query and a checkout-completion attempt, not a hang.
- `monolith`/`order-service` profiles: exercised for real only once step 9's Terraform output (RDS endpoint, SQS URL, order-service EC2 IP) exists — until then, verify only that `docker compose --profile monolith config` / `docker compose --profile order-service config` render without error (i.e. the profile wiring itself is correct), and note in the PR/commit that the cloud-pointed modes are untested until step 9 lands.

## Next step

`plans/steps/08-golden-fixture-tests.md`
