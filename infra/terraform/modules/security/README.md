# security

Both security groups this deployment needs. Split out on its own because
`rds`'s SG needs to reference `order_service`'s SG ID (ingress-by-SG, not by
CIDR) — keeping them together means that reference is a same-module resource
attribute, not a second cross-module wire.

No dependency on any other module — this is always the first module the root
instantiates.

## Inputs

| Name | Description | Type |
|---|---|---|
| `project_name` | Short name used to tag/name resources. | `string` |
| `vpc_id` | VPC to create the security groups in. | `string` |
| `my_ip_cidr` | Developer's public IP as a `/32` CIDR. Never widen this. | `string` |

## Outputs

| Name | Description |
|---|---|
| `order_service_sg_id` | Security group ID for the order-service EC2 instance. |
| `rds_sg_id` | Security group ID for the RDS instance. |

## Resources

- `aws_security_group.order_service` — ingress 22 + 8000 from `my_ip_cidr` only; egress all.
- `aws_security_group.rds` — ingress 5432 from `my_ip_cidr` (the monolith, running
  locally — see the root README's security note) **and** from `order_service`'s SG
  (order-service itself, in-VPC); egress all.
