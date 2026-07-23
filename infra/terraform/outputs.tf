output "order_service_public_ip" {
  description = "order-service EC2 instance's public IP."
  value       = module.order_service.public_ip
}

output "order_service_private_ip" {
  description = "order-service EC2 instance's private IP (VPC-internal)."
  value       = module.order_service.private_ip
}

output "rds_endpoint" {
  description = "RDS Postgres endpoint (host:port)."
  value       = module.rds.endpoint
}

output "sqs_queue_url" {
  description = "SQS queue URL -- feeds directly into CELERY_BROKER_URL."
  value       = module.sqs.queue_url
}

output "ssh_command" {
  description = "SSH into the order-service instance."
  value       = "ssh ubuntu@${module.order_service.public_ip}"
}

output "order_service_logs_command" {
  description = "Check order-service's container status/logs remotely."
  value       = "ssh ubuntu@${module.order_service.public_ip} 'cd /opt/saleor && sudo docker compose ps && sudo docker compose logs order-service --tail=50'"
}

output "env_cloud_snippet_for_local_monolith" {
  description = <<-EOT
    Copy-paste into .env.cloud (see docker-compose.yml's `monolith` profile,
    step 7) to point a locally-run monolith at this step's cloud resources.
    Still needs: SECRET_KEY, AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY (the
    Learner Lab session's exported credentials -- the developer's machine
    isn't running under LabInstanceProfile) -- see README.md.
  EOT
  value       = <<-EOT
    DATABASE_URL=postgres://${var.db_username}:${var.db_password}@${module.rds.endpoint}/saleor
    CELERY_BROKER_URL=sqs://
    AWS_DEFAULT_REGION=${var.aws_region}
    ORDER_SERVICE_URL=http://${module.order_service.public_ip}:8000
    ORDER_SERVICE_SHARED_SECRET=${var.order_service_shared_secret}
  EOT
  sensitive   = true
}
