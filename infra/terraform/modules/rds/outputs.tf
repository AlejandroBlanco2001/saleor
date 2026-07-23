output "endpoint" {
  description = "RDS Postgres endpoint (host:port)."
  value       = aws_db_instance.postgres.endpoint
}

output "address" {
  description = "RDS Postgres address (host only, no port)."
  value       = aws_db_instance.postgres.address
}

output "db_name" {
  description = "Database name."
  value       = aws_db_instance.postgres.db_name
}
