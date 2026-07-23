resource "aws_security_group" "order_service" {
  name        = "${var.project_name}-order-service-sg"
  description = "order-service EC2: SSH + app port from the developer's IP only"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH from developer IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "order-service HTTP API from developer IP (local monolith calls in from here)"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-order-service-sg"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "RDS: Postgres from the developer's IP (local monolith) and order-service's SG"
  vpc_id      = var.vpc_id

  # Deliberate lab-only loosening: the monolith runs on a developer's
  # machine, outside the VPC, so RDS must accept connections from its public
  # IP directly. Never widen my_ip_cidr beyond a single /32 — see the root
  # README's security note.
  ingress {
    description = "Postgres from developer IP (local monolith)"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description     = "Postgres from order-service (in-VPC)"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.order_service.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}
