# Step 9 — Terraform plan for AWS Academy Learner Lab

Depends on: Step 7 (working `docker-compose.yml`) as the reference topology. Independent of step 8.
See `plans/00-master-plan.md` for full context.

This step produces **Terraform code + a README**, not a live deployment. Actually running `terraform apply` against a real Learner Lab account is a separate, explicitly-confirmed action — do not run it automatically as part of this delivery.

## Constraints (why this design, not ECS/Fargate)

AWS Academy Learner Lab issues session-scoped credentials with IAM locked to the pre-provisioned `LabRole`/`LabInstanceProfile` — **no creating new IAM roles/policies**. Fargate needs a custom task execution role; ECS-with-ALB/ECR setups typically want custom IAM too. Sessions are also time-boxed (auto-terminate after a few hours) and region-restricted (`us-east-1` only). Fighting these constraints for a short-lived course experiment isn't worth it.

Chosen design: **two EC2 instances** (not one box, not ECS) + RDS.
- Splitting monolith and order-service across two instances demonstrates the architecture's actual selling point — independent deployability of order-service — which a single-box docker-compose deploy would not prove.
- EC2 (not Fargate) sidesteps the IAM restriction entirely — both instances just reuse the existing `LabInstanceProfile`.

## Files to create

```
infra/terraform/
  main.tf
  variables.tf
  outputs.tf
  user_data_monolith.sh.tpl
  user_data_order_service.sh.tpl
  README.md
  terraform.tfvars.example   # committed template; real terraform.tfvars is gitignored
```

## `main.tf` — resources (single flat config, no modules — small enough)

- `data "aws_vpc" "default"` + `data "aws_subnets"` (default VPC, always present in a Learner Lab account — no custom VPC needed).
- `data "aws_ami" "base"` — lookup, don't hardcode an AMI id (Amazon Linux 2023 or Ubuntu 22.04, whichever has simpler Docker install steps in `user_data`).
- `aws_security_group.monolith_sg` — ingress 22 (SSH, from a `var.my_ip` CIDR, not `0.0.0.0/0`), 8000 (Django, from `var.my_ip` or wider if needed for manual verification); egress all.
- `aws_security_group.order_service_sg` — ingress 22 (from `var.my_ip`), 8000 **only from `monolith_sg`** (`security_groups = [aws_security_group.monolith_sg.id]`, not a public CIDR) — matches the architecture's point that only the monolith talks to order-service; egress all.
- `aws_security_group.rds_sg` — ingress 5432 only from `monolith_sg` and `order_service_sg`.
- `aws_db_instance.postgres` — `engine = "postgres"`, `instance_class = "db.t3.micro"`, `publicly_accessible = false`, `vpc_security_group_ids = [aws_security_group.rds_sg.id]`, `db_name = "saleor"`, `username`/`password` from `var.db_username`/`var.db_password` (sensitive).
- `aws_instance.monolith` — `t3.medium`, `iam_instance_profile = "LabInstanceProfile"` (pre-existing — **never** define `aws_iam_role`/`aws_iam_instance_profile`, Learner Lab's SCP rejects it), `vpc_security_group_ids = [aws_security_group.monolith_sg.id]`, `user_data = templatefile("user_data_monolith.sh.tpl", { database_url = ..., order_service_url = "http://${aws_instance.order_service.private_ip}:8000" })`.
- `aws_instance.order_service` — `t3.small`, same `LabInstanceProfile`, `vpc_security_group_ids = [aws_security_group.order_service_sg.id]`, `user_data = templatefile("user_data_order_service.sh.tpl", { async_database_url = ..., django_events_url = "http://${aws_instance.monolith.private_ip}:8000/order-service/events/" })`.

Note the circular reference risk (`monolith`'s user_data needs `order_service`'s private_ip and vice versa) — Terraform resolves this fine since `private_ip` is known after instance creation, not before `user_data` renders at boot; both instances come up, then their startup scripts (which can retry/poll) write the final `.env` and start containers. If any ordering issue arises, use `aws_instance` static private IPs via `private_ip = "10.x.x.x"` (explicit, avoids relying on assignment-order values) instead of computed ones.

## `user_data_monolith.sh.tpl` / `user_data_order_service.sh.tpl`

Shell scripts: install Docker + Compose plugin, pull/copy the repo (or `git clone` if public, `scp`/`aws s3 cp` if private — call this out as a manual prerequisite in the README, don't bake credentials into `user_data`), write `.env` from the templated variables, then:
- monolith: `docker compose up -d web celeryworker redis` (subset of the `docker-compose.yml` from step 7 — `db` is replaced by RDS, `order-service` runs on the other box).
- order-service box: `docker compose up -d order-service`.

## `variables.tf`

`my_ip`, `db_username`, `db_password` (sensitive), `order_service_shared_secret` (sensitive) — all sourced from a gitignored `terraform.tfvars`, never hardcoded or committed. Provide `terraform.tfvars.example` with placeholder values.

## `outputs.tf`

Both instances' public IP/DNS + private IPs, RDS endpoint, and copy-pasteable SSH/`docker compose logs` commands to check status on each box.

## `README.md`

- Exact `terraform init` / `terraform plan` / `terraform apply` sequence.
- Learner Lab caveat: session credentials expire — if `apply` fails mid-way with an auth error, refresh the Learner Lab session's credentials and re-run (Terraform state lets it resume, doesn't restart from scratch).
- `terraform destroy` reminder before ending the lab session, to avoid a dangling RDS instance if the session doesn't fully reclaim resources.

## Verification

- `terraform validate` and `terraform fmt -check` pass with no AWS credentials needed.
- `terraform plan` runs clean against a real (or sandboxed) Learner Lab session, showing the expected resource list (2 security groups + RDS SG, 1 RDS instance, 2 EC2 instances) with no attempt to create an IAM role/policy anywhere in the plan output.
- (Explicit, separate, user-triggered) `terraform apply`, then confirm both instances' `docker compose ps` show healthy containers and a manual GraphQL query / checkout flow works end-to-end against the public IP of the monolith instance.

## This is the last step

After this, go back to `plans/00-master-plan.md`'s "Final verification" section.
