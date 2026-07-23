# Strangler Fig Increment 1 — `order-service` extraction (ORD-01 + ORD-02)

Master plan. Each numbered step has its own file in `plans/steps/` — read only the step you're working on to avoid burning context on the whole thing. Mark a step done by adding `[DONE]` to its title line in `plans/steps/0N-*.md` once verified.

## Context

MISO course modernization project on Saleor v2.11 (Django monolith). Prior deliverables (`context/entregas/w4`, `context/entregas/w7`) did the cartography, picked **Strangler Fig**, and scoped `order/` (highest cognitive complexity, active hotspot, smallest/most-bounded piece of the transactional cluster) as the extraction target. `context/entregas/w7/arquitectura-to-be.md` designed the target deployment (new `order-service`: FastAPI + async SQLAlchemy, same shared Postgres, Strangler Facade, Publish-Subscribe to `webhook/`, timeout+retry) and `context/entregas/w7/pre-experimento.md` scoped a first validation increment to order **creation + query** (ORD-01/ORD-02), leaving ORD-03..06 for later.

This delivery implements that first increment as real, running code. Confirmed scope: **only ORD-01 (create) + ORD-02 (query)**, State pattern present internally (unit-tested, no public endpoint yet), Publish-Subscribe to the existing webhook machinery, timeout+bounded-retry resilience, new `docker-compose.yml` (none exists today — creating one doesn't violate `CLAUD.md`'s "don't modify docker-compose.yml", nothing to modify), and a Terraform plan to provision two EC2 instances + RDS on AWS Academy Learner Lab (no Fargate — Learner Lab blocks custom IAM roles).

**Correction to the original design doc** (found during code exploration): there is no GraphQL `OrderCreate` mutation. Orders are created only via checkout completion (`saleor/checkout/complete_checkout.py::_create_order`) — that function, not a resolver, is the real creation seam. The query seam is real as designed: `saleor/graphql/order/resolvers.py::resolve_order` / `resolve_order_by_token`.

## Architecture recap

- **`order_service/`** (new top-level dir): FastAPI + SQLAlchemy async, own container, Python 3.11. Talks to the **same** Postgres (`order_order` table) Django already uses — no new tables, no migration, no Alembic.
- **Strangler Facade**, two seams:
  1. **Creation** — `_create_order()` stops doing `Order.objects.create(...)`, POSTs to order-service (does the INSERT), Django rehydrates an in-memory `Order` (`_state.adding = False`, pk set) so the rest of the function (line bulk-create, stock allocation, gift cards, payment reassignment, metadata save, `order_created()`) runs unchanged.
  2. **Query** — `resolve_order`/`resolve_order_by_token` stop doing the ORM SELECT for the root row, GET from order-service instead, rehydrate the same way. Nested fields (`lines`, `fulfillments`, `events`) keep working unchanged — reverse-FK managers keyed off `root.pk`, lazy-queried regardless of how `root` was built.
- **State pattern**: `OrderStatus` enum + `_VALID_TRANSITIONS` + `transition_order_status()` inside order-service — pure domain logic, unit tested, no public endpoint yet.
- **Publish-Subscribe**: order-service POSTs `{event_type, order_id}` to new Django endpoint `POST /order-service/events/`; that endpoint calls `saleor.order.actions.order_created(order, user)` — reuses existing `OrderEvent` audit-log + `PluginsManager` → `WebhookPlugin` → Celery chain unchanged.
- **Resilience**: Django→order-service HTTP client, short timeout + one bounded retry (`requests` + `urllib3.Retry`, already a dependency). Failures → controlled GraphQL error, never a hang.
- **docker-compose.yml** (new): `db`, `redis`, `web`, `celeryworker`, `order-service`, gated behind Compose **profiles** (`local`, `monolith`, `order-service`) so it can run three ways: everything local, monolith-only (`web`+`celeryworker`) pointed at AWS, or order-service-only pointed at AWS. See "Revised target deployment" below.
- **Terraform** (separate, AWS Learner Lab): RDS + SQS + **one** EC2 instance (order-service only) + security groups, `LabInstanceProfile`, no Fargate/ECR/ALB/custom IAM.

## Revised target deployment (decided after step 6, before step 7)

Original design (Terraform provisioning two EC2 boxes, one per service, both talking over a private VPC) is replaced. Actual target: **the monolith (`web` + `celeryworker`) runs on the developer's machine** (natively or via the `monolith` Compose profile), pointed at cloud-hosted dependencies over the public internet. Only `order-service` gets deployed to AWS.

- **Database**: AWS RDS Postgres. Since the monolith runs outside the VPC (developer's laptop, not EC2), RDS must be reachable from the public internet — `publicly_accessible = true`, but its security group only opens 5432 to `var.my_ip` (developer IP) and the `order_service_sg` (same-VPC EC2 instance), never `0.0.0.0/0`.
- **Queue**: AWS SQS (`kombu`'s `sqs://` transport — `boto3` is already a pinned dependency, no new package needed). Celery's broker becomes an SQS queue URL instead of Redis; no server to run/manage. The `local` Compose profile still uses a plain `redis` container for pure-local runs — no reason to require AWS for a fully-local dev loop.
- **order-service**: still deployed to a single EC2 instance (Learner Lab IAM constraints — see step 9 — rule out Fargate/ECS regardless of this change; EC2 stays the simplest path). Its security group opens 8000 to `var.my_ip` too (the monolith calling it is no longer in-VPC, so `security_groups = [monolith_sg.id]` no longer applies — there is no `monolith_sg` anymore).
- **Local dev**, three explicit modes via `docker-compose.yml` profiles:
  1. `local` — full stack, nothing touches AWS (`db`, `redis`, `web`, `celeryworker`, `order-service` all containers). This is what steps 1-6's tests already exercise.
  2. `monolith` — only `web`+`celeryworker` run (locally, in Docker or natively), `.env` points `DATABASE_URL` at RDS, `CELERY_BROKER_URL` at SQS, `ORDER_SERVICE_URL` at the EC2 instance's address.
  3. `order-service` — only the `order-service` container runs, `.env` points `ASYNC_DATABASE_URL` at RDS, `DJANGO_EVENTS_URL` at wherever the monolith is currently reachable (developer's own public IP/tunnel, since it's not a fixed cloud address in this mode — call this out as a real limitation in step 7, not solved silently).

## Step index

1. `plans/steps/01-order-service-domain-db.md` — order-service domain (State pattern) + SQLAlchemy DB layer, no HTTP yet.
2. `plans/steps/02-order-service-http-layer.md` — FastAPI routers/schemas/app wiring.
3. `plans/steps/03-pubsub-webhook-wiring.md` — event publisher (order-service) + Django event-intake endpoint.
4. `plans/steps/04-django-http-client.md` — Django→order-service HTTP client, timeout+retry.
5. `plans/steps/05-query-facade.md` — Strangler Facade for `resolve_order`/`resolve_order_by_token`.
6. `plans/steps/06-creation-facade.md` — Strangler Facade for `_create_order()`.
7. `plans/steps/07-docker-compose.md` — `docker-compose.yml` (profile-gated: local / monolith-only / order-service-only) + `order_service/Dockerfile`.
8. `plans/steps/08-golden-fixture-tests.md` — parity tests, legacy vs. facade.
9. `plans/steps/09-terraform-aws.md` — Terraform plan for AWS Academy Learner Lab (RDS + SQS + order-service EC2 only).

Do them in order — each depends on the previous being done and tested. Steps 1-4 have no dependency on Django facade code and can be built/tested in isolation first; steps 5-6 are the risky Django edits and should only start once 1-4 are verified working.

## Critical files (referenced across steps)

- `saleor/checkout/complete_checkout.py` (`_create_order`, lines 229-284) — creation seam
- `saleor/graphql/order/resolvers.py` (`resolve_order`, `resolve_order_by_token`) — query seam
- `saleor/graphql/order/types.py` (`Order` type, `resolve_billing_address`/`resolve_lines`/`resolve_fulfillments`/`resolve_events`) — confirms nested fields work unchanged off `root.pk`
- `saleor/order/models.py` (`Order` model) — authoritative column/default list for SQLAlchemy mapping
- `saleor/order/actions.py` (`order_created`) and `saleor/plugins/webhook/plugin.py` — existing dispatch chain the new event endpoint must reuse unchanged
- `saleor/urls.py` — wiring for the new internal event-intake endpoint
- `saleor/settings.py` — `DATABASES`/env-var convention to mirror; new `ORDER_SERVICE_*` settings
- `Dockerfile` and `Procfile` (repo root) — patterns to mirror in `order_service/Dockerfile` and `docker-compose.yml`
- New: `order_service/`, `docker-compose.yml`, `saleor/order/order_service_client.py`, `saleor/order/views.py`, `infra/terraform/`

## Final verification (after all 9 steps)

1. `order_service/` unit + API tests pass standalone (`pytest order_service/tests/`).
2. Django facade tests pass with the client mocked (`pytest saleor/checkout/tests/test_checkout_complete.py saleor/graphql/order/tests/test_order_service_facade.py`).
3. `docker-compose --profile local up` brings up all 5 services; `docker-compose exec web python manage.py migrate` succeeds; a manual GraphQL `order(id:...)` query and a full checkout-completion flow both work end-to-end against the composed stack, hitting the real `order-service` container.
4. Kill/pause the `order-service` container mid-test and confirm the monolith returns a controlled GraphQL/checkout error within the configured timeout, not a hang.
5. Golden-fixture diff shows 100% parity on the happy-path queries.
6. (Optional, explicit trigger only) `terraform plan` in `infra/terraform/` runs clean against a real Learner Lab session before ever running `apply`. Then (also explicit trigger only) `terraform apply`, run the `monolith` Compose profile locally against the resulting RDS/SQS/order-service outputs, and confirm the same checkout-completion + query flow works end-to-end over the public internet.
