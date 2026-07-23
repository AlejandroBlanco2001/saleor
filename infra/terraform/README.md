# infra/terraform — order-service on AWS Academy Learner Lab

Provisions: RDS Postgres (`publicly_accessible = true`), an SQS queue (Celery broker),
and one EC2 instance running `order-service` (via step 7's `order-service` Compose
profile). The monolith (`web`+`celeryworker`) is **not** deployed here — it runs on
your own machine, pointed at these resources over the public internet (step 7's
`monolith` Compose profile). See `plans/00-master-plan.md`'s "Revised target
deployment" section for the full rationale.

## Module architecture

Root module wires 4 child modules together. Each has its own README with a full
inputs/outputs table (`modules/<name>/README.md`) — this section is just the graph:

```
data.aws_vpc.default, data.aws_subnets.default   (root — shared VPC lookup)
        |
        v
  module.security  (2 security groups, no dependencies)
        |
        +--(rds_sg_id)-------------> module.rds  (Postgres, publicly_accessible)
        |                                  |
        +--(order_service_sg_id)--+        | (endpoint)
                                   v        v
                          module.order_service  (EC2, bootstrapped via user_data)

  module.sqs  (Celery broker queue — standalone, not wired to any other AWS resource)
```

Why split this way rather than one flat file (the original single-file design): the
one genuine cross-resource dependency here is `rds`'s security group needing
`order_service`'s security group ID for an ingress-by-SG rule, and `order_service`'s
`user_data` needing `rds`'s endpoint. Keeping both security groups in one `security`
module (instead of colocating each SG with its own resource) avoids that turning into
a two-directional module dependency, which Terraform doesn't allow between modules
(no cycles). `sqs` has zero dependencies on anything else and is split out purely
because it's a distinct concern (Celery broker, not part of the order-service
deployment itself) — it just happens to not need wiring into the other modules.

Each module is self-contained and reusable on its own (e.g. `modules/rds` doesn't
know anything about order-service specifically) — the root module is the only place
that knows the full picture.

## Before you run anything

**Unverified assumption, check first**: this design assumes the Learner Lab's
`LabRole`/`LabInstanceProfile` has SQS permissions (`SendMessage`/`ReceiveMessage`/
`DeleteMessage`/`GetQueueUrl`/`GetQueueAttributes` at minimum). Academy lab roles
vary by course — verify before relying on this:
```
aws iam list-attached-role-policies --role-name LabRole
```
If SQS isn't permitted and can't be added (Learner Lab blocks custom IAM policies),
this design needs revisiting — e.g. supplying long-lived SQS credentials via env vars
instead of relying on the instance profile, or picking a different broker.

## Prerequisites

- A live AWS Academy Learner Lab session (credentials exported to your shell —
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`).
- Your public IP (for `var.my_ip`) — `curl -s https://checkip.amazonaws.com`.
- `terraform.tfvars` filled in from `terraform.tfvars.example` (gitignored, never commit
  the real one).
- `infra/terraform/modules/order_service/user_data.sh.tpl`'s `git clone <YOUR_REPO_URL>`
  line needs a real reachable repo URL (public git remote), or adjust that section to
  `scp`/`aws s3 cp` the code onto the instance instead — don't bake credentials into
  `user_data` either way (it's visible via the EC2 console/metadata API to anyone
  with instance access).

## Run it — the fast path (`scripts/cloud_dev.py`, also `.sh`/`.bat`)

`scripts/cloud_dev.py` (repo root) drives this Terraform config **and** step 7's
`monolith` Compose profile together, so provisioning the cloud side and pointing a
local monolith at it is a couple of commands instead of a manual multi-step dance.
Runnable by a human or an agent — every billed/destructive action needs an explicit
`--yes`, everything else is safe to run blind (`plan`/`status` touch nothing).

```
# from the repo root
python scripts/cloud_dev.py plan              # terraform init + plan, read-only
python scripts/cloud_dev.py apply --yes        # terraform init + apply -auto-approve
python scripts/cloud_dev.py wire               # writes .env.cloud from terraform output + this shell's AWS creds
python scripts/cloud_dev.py start              # ENV_FILE=.env.cloud docker compose --profile monolith up -d
python scripts/cloud_dev.py all --yes           # apply + wire + start in one go
python scripts/cloud_dev.py status             # terraform output, read-only
python scripts/cloud_dev.py stop               # docker compose --profile monolith down
python scripts/cloud_dev.py destroy --yes       # terraform destroy
```
Same commands work via `scripts/cloud_dev.sh` (POSIX) or `scripts\cloud_dev.bat`
(Windows) — thin wrappers around the same Python. Every command still needs
`terraform.tfvars` filled in and, for anything touching AWS, the Learner Lab
session's `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` exported —
the script checks both up front and fails with a clear message rather than a
half-done apply.

## Run it — the manual path

Equivalent to the above, spelled out step by step (what the script actually runs):

```
cd infra/terraform
terraform init
terraform plan    # review the resource list before applying
terraform apply
terraform output -raw env_cloud_snippet_for_local_monolith   # see below
```

`terraform plan`/`apply` need real AWS credentials; `terraform validate` and
`terraform fmt -check` do not.

Session credentials expire mid-lab — if `apply` fails partway with an auth error,
refresh the Learner Lab session's credentials and re-run `terraform apply`. Terraform
state lets it resume from where it left off, it doesn't restart from scratch.

### Point your local monolith at it, manually

Paste `terraform output -raw env_cloud_snippet_for_local_monolith`'s result into
`.env.cloud` at the repo root (see `docker-compose.yml`'s `monolith` profile from
step 7), then fill in the two things the snippet doesn't have:
- `SECRET_KEY` — any value for a lab session, a real secret for anything longer-lived.
- `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` — the Learner Lab
  session's own exported credentials. Your machine isn't running under
  `LabInstanceProfile`, so it needs actual credentials for the SQS client, unlike the
  EC2 side. These expire with the lab session — `CELERY_BROKER_URL`/SQS calls will
  start failing then, same failure mode as any other session timeout, not a bug.
  (`scripts/cloud_dev.py wire` fills in all three of these from the current shell
  automatically — this manual step is only needed without it.)

Then: `ENV_FILE=.env.cloud docker compose --profile monolith up`.

## Security note (lab-only tradeoff, not a production pattern)

The `security` module's `aws_security_group.rds` allows Postgres from `var.my_ip`
directly — RDS is reachable from outside the VPC because the monolith runs on a
developer's laptop, not inside AWS. Keep `var.my_ip` a single `/32`, never widen it.
This tradeoff only makes sense for a short-lived course lab; a real deployment would
keep the app server inside the VPC and RDS private.

## Tear down

```
terraform destroy
```
or `python scripts/cloud_dev.py destroy --yes`. Do this before ending the lab
session — Learner Lab sessions don't always reclaim resources cleanly, and a
dangling RDS instance left running past session end is easy to lose track of.
