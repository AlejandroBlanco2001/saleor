output "queue_url" {
  description = "SQS queue URL — feeds into the local monolith's CELERY_BROKER_URL."
  value       = aws_sqs_queue.celery_broker.url
}

output "queue_arn" {
  description = "SQS queue ARN."
  value       = aws_sqs_queue.celery_broker.arn
}
