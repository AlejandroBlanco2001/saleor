variable "project_name" {
  description = "Short name used to tag/name resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC to create the security groups in."
  type        = string
}

variable "my_ip_cidr" {
  description = "Developer's public IP as a /32 CIDR. Never widen this to 0.0.0.0/0 — see the root README's security note."
  type        = string
}
