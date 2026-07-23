variable "project_name" {
  description = "Short name used to tag/name resources."
  type        = string
}

variable "subnet_id" {
  description = "Subnet to launch the instance in."
  type        = string
}

variable "security_group_id" {
  description = "Security group to attach (from the security module)."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.small"
}

variable "ami_owner" {
  description = "AMI owner ID to look up the base image from. Default is Canonical's, for Ubuntu 22.04."
  type        = string
  default     = "099720109477"
}

variable "ami_name_filter" {
  description = "AMI name filter. Default matches Ubuntu 22.04 (Jammy) amd64 HVM images — user_data.sh.tpl's Docker install steps are Ubuntu-specific, so changing this needs matching changes there too."
  type        = string
  default     = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
}

variable "async_database_url" {
  description = "postgresql+asyncpg:// URL order-service connects to (built by the root module from the rds module's output)."
  type        = string
  sensitive   = true
}

variable "django_events_url" {
  description = "Where order-service POSTs order-created events back to — wherever the local monolith is currently reachable from. See the root README's known-gap note."
  type        = string
}

variable "order_service_shared_secret" {
  description = "Shared secret order-service sends via X-Internal-Token; must match the local monolith's ORDER_SERVICE_SHARED_SECRET."
  type        = string
  sensitive   = true
}
