# Step 9 — Terraform plan for AWS Academy Learner Lab (RDS + SQS + order-service EC2)

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

```
infra/terraform/
  main.tf
  variables.tf
  outputs.tf
  user_data_order_service.sh.tpl
  README.md
  terraform.tfvars.example   # committed template; real terraform.tfvars is gitignored
```

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

## Verification

- `terraform validate` and `terraform fmt -check` pass with no AWS credentials needed.
- `terraform plan` runs clean against a real (or sandboxed) Learner Lab session, showing the expected resource list (2 security groups, 1 RDS instance, 1 SQS queue, 1 EC2 instance) with no attempt to create an IAM role/policy anywhere in the plan output.
- (Explicit, separate, user-triggered) `terraform apply`, then: `docker compose ps` on the order-service instance shows a healthy container; from the developer's machine, `ENV_FILE=.env.cloud docker compose --profile monolith up` (using the generated `.env.cloud` snippet) brings up a working monolith that reaches RDS, SQS, and the order-service EC2 instance; a manual GraphQL query and a full checkout-completion flow both work end-to-end.

## This is the last step

After this, go back to `plans/00-master-plan.md`'s "Final verification" section.
