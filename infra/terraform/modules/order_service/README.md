# order_service

The one thing actually deployed to AWS: an EC2 instance running order-service
via step 7's `order-service` Compose profile, bootstrapped entirely through
`user_data.sh.tpl` (installs Docker, clones the repo, writes `.env.cloud`
from the templated variables, `docker compose --profile order-service up -d`).

AMI is looked up (`data.aws_ami.base`, Ubuntu 22.04/Jammy by default), never
hardcoded — `ami_owner`/`ami_name_filter` are overridable, but the shipped
`user_data.sh.tpl` assumes Ubuntu's `apt`-based Docker install, so changing
the AMI family means updating that script too.

Depends on: `security` module (`security_group_id`), `rds` module
(`async_database_url`, built by the root module from `rds`'s `endpoint`
output — this module has no direct dependency on the `rds` module itself,
just on a string the root module assembles).

## Inputs

| Name | Description | Type | Default |
|---|---|---|---|
| `project_name` | Short name used to tag/name resources. | `string` | — |
| `subnet_id` | Subnet to launch the instance in. | `string` | — |
| `security_group_id` | Security group to attach (from `security`). | `string` | — |
| `instance_type` | EC2 instance type. | `string` | `"t3.small"` |
| `ami_owner` | AMI owner ID. | `string` | `"099720109477"` (Canonical) |
| `ami_name_filter` | AMI name filter. | `string` | Ubuntu 22.04 Jammy amd64 HVM |
| `async_database_url` | `postgresql+asyncpg://` URL. | `string` (sensitive) | — |
| `django_events_url` | Where order-service POSTs events back to. | `string` | — |
| `order_service_shared_secret` | Shared secret for the event-intake callback. | `string` (sensitive) | — |

## Outputs

| Name | Description |
|---|---|
| `public_ip` | What the local monolith's `ORDER_SERVICE_URL` points at. |
| `private_ip` | VPC-internal IP (unused by the current design — the caller is outside the VPC — kept for reference/debugging from a bastion-style SSH session). |
| `instance_id` | EC2 instance ID. |

## Manual prerequisite

`user_data.sh.tpl`'s `git clone <YOUR_REPO_URL>` line needs a real reachable
repo URL, or that section needs adjusting to `scp`/`aws s3 cp` the code onto
the instance instead. Deliberately not baked into Terraform variables —
don't put credentials in `user_data`, it's visible via the EC2 console/
instance metadata API to anyone with instance access. See the root README.
