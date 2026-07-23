variable "project_name" {
  description = "Short name used to tag/name resources."
  type        = string
  default     = "saleor-order-service"
}

variable "aws_region" {
  description = "AWS Academy Learner Lab sessions are region-restricted to us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "my_ip" {
  description = "Developer's public IP, as a /32 CIDR (e.g. \"203.0.113.7/32\"). Never widen this to 0.0.0.0/0."
  type        = string
}

variable "db_username" {
  description = "RDS Postgres master username."
  type        = string
  default     = "saleor"
}

variable "db_password" {
  description = "RDS Postgres master password."
  type        = string
  sensitive   = true
}

variable "order_service_shared_secret" {
  description = "Value order-service sends via X-Internal-Token when calling back into Django's /order-service/events/. Must match Django's ORDER_SERVICE_SHARED_SECRET."
  type        = string
  sensitive   = true
}

variable "django_events_url" {
  description = <<-EOT
    Where order-service should POST order-created events back to -- i.e.
    wherever the LOCAL monolith (developer's machine, step 7's `monolith`
    Compose profile) is currently reachable from. There is no fixed cloud
    address for this (see plans/steps/07-docker-compose.md's "known gap"
    note) -- use a tunnel (ngrok/Cloudflare Tunnel/SSH reverse tunnel) URL,
    or accept the webhook round-trip is best-effort if left as the
    placeholder default.
  EOT
  type        = string
  default     = "http://CHANGE-ME-tunnel-to-local-monolith.example:8000/order-service/events/"
}

variable "instance_type" {
  description = "EC2 instance type for order-service."
  type        = string
  default     = "t3.small"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}
