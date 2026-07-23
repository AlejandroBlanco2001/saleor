# rds

A single `db.t3.micro` RDS Postgres instance, `publicly_accessible = true` —
required because the monolith (step 7's `monolith` Compose profile) runs on
a developer's machine, outside the VPC. Actual access is restricted by the
security group passed in via `security_group_id` (see the `security`
module), not by this module — `publicly_accessible` just controls whether
AWS assigns a public endpoint at all.

Depends on: `security` module (needs its `rds_sg_id` output).

## Inputs

| Name | Description | Type | Default |
|---|---|---|---|
| `project_name` | Short name used to tag/name resources. | `string` | — |
| `security_group_id` | Security group to attach (from the `security` module). | `string` | — |
| `instance_class` | RDS instance class. | `string` | `"db.t3.micro"` |
| `allocated_storage` | Allocated storage, in GB. | `number` | `20` |
| `db_username` | Master username. | `string` | `"saleor"` |
| `db_password` | Master password. | `string` (sensitive) | — |

## Outputs

| Name | Description |
|---|---|
| `endpoint` | `host:port` — what `order_service`'s module uses to build `ASYNC_DATABASE_URL`. |
| `address` | Host only, no port. |
| `db_name` | Database name (`"saleor"`, fixed). |
