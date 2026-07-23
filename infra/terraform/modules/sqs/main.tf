resource "aws_sqs_queue" "celery_broker" {
  name = "${var.project_name}-celery-broker"

  tags = {
    Name = "${var.project_name}-celery-broker"
  }
}
