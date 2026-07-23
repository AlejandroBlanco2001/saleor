resource "aws_db_instance" "postgres" {
  identifier        = "${var.project_name}-db"
  engine            = "postgres"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  db_name           = "saleor"
  username          = var.db_username
  password          = var.db_password
  # publicly_accessible = true is deliberate here, not a default worth
  # hiding behind a variable — the monolith runs outside the VPC (on a
  # developer's machine), so RDS must be reachable from the public internet.
  # The security module's SG is what actually restricts who can reach it.
  publicly_accessible    = true
  vpc_security_group_ids = [var.security_group_id]
  skip_final_snapshot    = true

  tags = {
    Name = "${var.project_name}-db"
  }
}
