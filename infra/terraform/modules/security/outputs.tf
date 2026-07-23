output "order_service_sg_id" {
  description = "Security group ID for the order-service EC2 instance."
  value       = aws_security_group.order_service.id
}

output "rds_sg_id" {
  description = "Security group ID for the RDS instance."
  value       = aws_security_group.rds.id
}
