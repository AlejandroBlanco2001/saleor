output "public_ip" {
  description = "Public IP — what the local monolith's ORDER_SERVICE_URL points at."
  value       = aws_instance.order_service.public_ip
}

output "private_ip" {
  description = "Private (VPC-internal) IP."
  value       = aws_instance.order_service.private_ip
}

output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.order_service.id
}
