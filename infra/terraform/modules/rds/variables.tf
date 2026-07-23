variable "project_name" {
  description = "Short name used to tag/name resources."
  type        = string
}

variable "security_group_id" {
  description = "Security group to attach to the RDS instance (from the security module)."
  type        = string
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "RDS allocated storage, in GB."
  type        = number
  default     = 20
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
