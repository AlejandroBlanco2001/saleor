# Setup: Running docker-compose

Services and their profiles (`docker-compose.yml`):

| service        | profiles                  | notes                              |
|----------------|----------------------------|-------------------------------------|
| db             | local                      | Postgres, only for full local stack |
| redis          | local                      | only for full local stack           |
| web            | local, monolith            | Saleor monolith (port 8000)         |
| celeryworker   | local, monolith            | Celery worker for monolith          |
| order-service  | local, order-service       | standalone order service (port 8001)|

Env file used: `${ENV_FILE:-.env.local}`. Copy `.env.local.example` → `.env.local` first if missing. Key var linking monolith → order-service: `ORDER_SERVICE_URL=http://order-service:8000` in `.env.local`.

## 1. Just order-service

Runs order-service alone, no monolith/db/redis.

```bash
docker compose --profile order-service up --build
```

Reachable at `http://localhost:8001`.

## 2. order-service + monolith (linked)

Runs `web` + `celeryworker` (monolith) together with `order-service`. Monolith talks to order-service via `ORDER_SERVICE_URL` env var.

```bash
docker compose --profile monolith --profile order-service up --build
```

Note: this combo alone has no db/redis — monolith needs those unless pointed at external ones. If you need db/redis too, use `local` profile instead (see below) or add `--profile local` alongside.

## 3. Just monolith

Runs only `web` + `celeryworker`, no order-service, no db/redis.

```bash
docker compose --profile monolith up --build
```

Note: without db/redis (not in `monolith` profile), `web`/`celeryworker` need `DATABASE_URL`/`REDIS_URL` pointing to external instances, or run with `local` profile added:

```bash
docker compose --profile monolith --profile local up --build
```

## Full local stack (reference)

All services: db, redis, web, celeryworker, order-service.

```bash
docker compose --profile local up --build
```
