# Step 9 — Terraform plan for AWS Academy Learner Lab (RDS + SQS + order-service EC2) [DONE]

Depends on: Step 7 (working `docker-compose.yml`, specifically the `order-service` and `monolith` profiles) as the reference topology. Independent of step 8.
See `plans/00-master-plan.md` for full context, especially "Revised target deployment".

This step produces **Terraform code + a README**, not a live deployment. Actually running `terraform apply` against a real Learner Lab account is a separate, explicitly-confirmed action — do not run it automatically as part of this delivery.

## What changed from the original design

The monolith (`web` + `celeryworker`) is **not deployed to AWS** — it runs on the developer's machine (the `monolith` Compose profile from step 7), pointed at AWS-hosted dependencies over the public internet. Terraform therefore only provisions:

- RDS Postgres (must be `publicly_accessible = true` now — the monolith isn't in the VPC)
- An SQS queue (Celery broker)
- One EC2 instance for `order-service` (still needs to run *somewhere* reachable by both the local monolith and, in Learner Lab's time-boxed sessions, whoever's testing)

No monolith EC2 instance, no `monolith_sg`.

## Constraints (why this design, not ECS/Fargate)

AWS Academy Learner Lab issues session-scoped credentials with IAM locked to the pre-provisioned `LabRole`/`LabInstanceProfile` — **no creating new IAM roles/policies**. Fargate needs a custom task execution role; ECS-with-ALB/ECR setups typically want custom IAM too. Sessions are also time-boxed (auto-terminate after a few hours) and region-restricted (`us-east-1` only). Fighting these constraints for a short-lived course experiment isn't worth it — same reasoning as before, EC2 for `order-service` still stands.

**Verify before writing `main.tf`**: confirm `LabRole`/`LabInstanceProfile` actually has `sqs:*` (or at least `SendMessage`/`ReceiveMessage`/`DeleteMessage`/`GetQueueUrl`/`GetQueueAttributes`) permissions in this Learner Lab account — Academy lab roles vary by course. If not, the SQS approach needs revisiting (e.g. long-poll credentials via env vars instead of the instance profile) — don't assume, check the actual attached policy first (`aws iam list-attached-role-policies --role-name LabRole` if the Lab CLI access allows it, otherwise ask whoever administers the Learner Lab account).

## Files to create

Refactored into modules after the initial single-file version (user request:
"modern module architecture, and documented") — final layout:

```
infra/terraform/
  main.tf              # provider, shared data sources, module wiring only
  variables.tf
  outputs.tf
  README.md            # includes the module dependency graph
  terraform.tfvars.example   # committed template; real terraform.tfvars is gitignored
  modules/
    security/     # both security groups (main.tf, variables.tf, outputs.tf, README.md)
    rds/          # RDS Postgres instance
    sqs/          # Celery broker queue
    order_service/     # EC2 instance + user_data.sh.tpl (moved in from root)
```

Module dependency graph (see root `README.md` for the full explanation of why
it's split this way, specifically why both security groups live in one
module): `security` → `rds` → `order_service` (via `rds`'s `endpoint`
output); `security` → `order_service` directly (its own SG); `sqs` has no
dependencies on anything else.

## `main.tf` — resources (single flat config, no modules — small enough)

- `data "aws_vpc" "default"` + `data "aws_subnets"` (default VPC, always present in a Learner Lab account — no custom VPC needed).
- `data "aws_ami" "base"` — lookup, don't hardcode an AMI id (Amazon Linux 2023 or Ubuntu 22.04, whichever has simpler Docker install steps in `user_data`).
- `aws_security_group.order_service_sg` — ingress 22 (SSH, from `var.my_ip`), ingress 8000 from `var.my_ip` (the monolith now calls in from outside the VPC, not from a sibling `monolith_sg` — there isn't one anymore); egress all.
- `aws_security_group.rds_sg` — ingress 5432 from `var.my_ip` (monolith, running locally) **and** from `order_service_sg` (order-service, in-VPC). This is the one deliberate security loosening this redesign requires — RDS is no longer reachable only from inside the VPC. Keep the CIDR as narrow as `var.my_ip/32` (a single developer IP), never `0.0.0.0/0`; call this out explicitly in the README as a course-lab-only tradeoff, not a production pattern.
- `aws_db_instance.postgres` — `engine = "postgres"`, `instance_class = "db.t3.micro"`, `publicly_accessible = true`, `vpc_security_group_ids = [aws_security_group.rds_sg.id]`, `db_name = "saleor"`, `username`/`password` from `var.db_username`/`var.db_password` (sensitive).
- `aws_sqs_queue.celery_broker` — standard queue (no need for FIFO), default visibility timeout is fine to start; name it something identifiable (`"${var.project_name}-celery-broker"`).
- `aws_instance.order_service` — `t3.small`, `iam_instance_profile = "LabInstanceProfile"` (pre-existing — **never** define `aws_iam_role`/`aws_iam_instance_profile`, Learner Lab's SCP rejects it), `vpc_security_group_ids = [aws_security_group.order_service_sg.id]`, `user_data = templatefile("user_data_order_service.sh.tpl", { async_database_url = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/saleor", django_events_url = var.django_events_url })`.

`var.django_events_url` is a plain input variable now (not derived from a sibling instance's `private_ip`, since there is no sibling instance) — the developer supplies wherever their local monolith is reachable from (a tunnel URL, most likely; see step 7's "known gap" note). Default it to an obviously-placeholder value so `terraform plan` doesn't silently succeed with a bogus real-looking URL.

## `user_data_order_service.sh.tpl`

Shell script: install Docker + Compose plugin, pull/copy the repo (`git clone` if public, `scp`/`aws s3 cp` if private — call this out as a manual prerequisite in the README, don't bake credentials into `user_data`), write `.env.cloud` from the templated variables (`ASYNC_DATABASE_URL`, `DJANGO_EVENTS_URL`, `ORDER_SERVICE_SHARED_SECRET`), then:
`ENV_FILE=.env.cloud docker compose --profile order-service up -d` (the `order-service`-only profile from step 7).

## `variables.tf`

`my_ip`, `db_username`, `db_password` (sensitive), `order_service_shared_secret` (sensitive), `django_events_url` (string, placeholder default) — all sourced from a gitignored `terraform.tfvars`, never hardcoded or committed. Provide `terraform.tfvars.example` with placeholder values.

## `outputs.tf`

- `order_service`'s public IP/DNS and private IP.
- RDS endpoint.
- The SQS queue URL (feeds directly into the monolith's local `CELERY_BROKER_URL=sqs://...` — print the exact value to copy-paste, not just the ARN).
- Copy-pasteable SSH / `docker compose logs` command for the order-service instance.
- A copy-pasteable `.env.cloud` snippet for the developer's **local** `monolith` profile, assembled from the above (`DATABASE_URL`, `CELERY_BROKER_URL`, `ORDER_SERVICE_URL`) — this is the actual bridge between this step's cloud output and step 7's local `monolith` profile, worth generating directly rather than making the developer hand-assemble it.

## `README.md`

- Exact `terraform init` / `terraform plan` / `terraform apply` sequence.
- How to point the local `monolith` Compose profile (step 7) at this step's outputs: copy the generated `.env.cloud` snippet from `terraform output`, done.
- AWS credentials for the **local** Celery/SQS client (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION` in `.env.cloud`) — the developer's machine isn't running under `LabInstanceProfile`, so it needs the Learner Lab session's exported credentials, not the instance-profile chain the EC2 side uses. Session credentials expire with the lab session — note that `CELERY_BROKER_URL`/SQS calls will start failing when that happens, same failure mode as any other Learner Lab session timeout.
- Learner Lab caveat: session credentials expire — if `apply` fails mid-way with an auth error, refresh the Learner Lab session's credentials and re-run (Terraform state lets it resume, doesn't restart from scratch).
- `terraform destroy` reminder before ending the lab session, to avoid a dangling RDS instance if the session doesn't fully reclaim resources.

## Verification — actually run, results below

- `terraform fmt -check -diff` → clean, no output.
- `terraform init -backend=false` → succeeds, `aws` provider ~> 5.0 installed.
- `terraform validate` → **Success! The configuration is valid.**
- `terraform plan` with dummy var values (no real Learner Lab session available in this environment) → fails at the expected point: `Retrieving AWS account details: ... InvalidClientTokenId` — confirms the resource graph itself builds cleanly (all references resolve, no cycles) and the only thing blocking a real plan is actual AWS credentials, exactly as expected without a live Learner Lab session. A full `terraform plan`/`apply` against a real session is still the explicit, separate, user-triggered step described above — not run here.
- Not independently re-verified: whether `LabRole`/`LabInstanceProfile` actually has SQS permissions (flagged in this file's "Constraints" section and in `README.md` as something to check with a real session before trusting the SQS approach) — no live AWS access in this environment to check it.

**Deviations from the plan's literal file list**, both harmless: `main.tf` includes a `terraform { required_providers { aws } }` block and `provider "aws" {}` (needed for `init`/`validate` to work at all, the plan's resource list implied but didn't spell out); AMI lookup pins Ubuntu 22.04 explicitly (Canonical owner ID `099720109477`) rather than leaving the choice open, since the `user_data` script's Docker install steps are Ubuntu-specific (`apt`, Docker's official Ubuntu repo).

**Refactored into modules on request** (after the above was already working as one flat config): `security`/`rds`/`sqs`/`order_service`, each with its own `README.md` (inputs/outputs tables, dependency notes). Re-ran the full verification after the refactor — `fmt`/`init`/`validate` all clean, `terraform graph` confirms the dependency edges match the documented graph (`security.rds_sg` depends on `security.order_service_sg` in-module; `rds` depends on `security`'s output; `order_service` depends on `rds`'s `endpoint` output), `plan` with dummy vars still resolves the whole graph and fails only at the AWS auth boundary, same as before the refactor.

**Added on request, also after the above**: `scripts/cloud_dev.py` (+ `.sh`/`.bat` wrappers) drives this Terraform config and step 7's `monolith` Compose profile together — `plan`/`apply`/`wire`/`start`/`status`/`stop`/`destroy`/`all` subcommands, every billed/destructive one gated behind an explicit `--yes` so it's safe for an agent to run unattended otherwise. `wire` builds `.env.cloud` straight from `terraform output -json` plus the current shell's AWS creds (needs `AWS_SESSION_TOKEN` too — Learner Lab issues temporary STS creds, not just a key/secret pair — added to `.env.cloud.example` as well). Smoke-tested all the fast-fail paths for real: missing `terraform.tfvars` → clean error + exit 1; missing AWS env vars → clean error + exit 1; `apply` without `--yes` → falls back to `plan` instead of applying. Full `apply`/`wire`/`start` path not run end-to-end (needs a real Learner Lab session, same limitation as the rest of this step).

## This is the last step

After this, go back to `plans/00-master-plan.md`'s "Final verification" section.
