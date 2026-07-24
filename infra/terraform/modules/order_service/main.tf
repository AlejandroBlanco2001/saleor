data "aws_ami" "base" {
  most_recent = true
  owners      = [var.ami_owner]

  filter {
    name   = "name"
    values = [var.ami_name_filter]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Ephemeral keypair so the experiment run can SSH in to verify/debug the
# instance's bootstrap (user_data logs, container status) -- generated fresh
# per apply rather than requiring a pre-existing AWS keypair in the Learner
# Lab account.
resource "tls_private_key" "order_service" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "order_service" {
  key_name   = "${var.project_name}-order-service-key"
  public_key = tls_private_key.order_service.public_key_openssh
}

resource "local_sensitive_file" "order_service_private_key" {
  content         = tls_private_key.order_service.private_key_pem
  filename        = "${path.root}/order_service_key.pem"
  file_permission = "0600"
}

resource "aws_instance" "order_service" {
  ami                    = data.aws_ami.base.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  key_name               = aws_key_pair.order_service.key_name
  # Pre-existing Learner Lab role — never define aws_iam_role/aws_iam_instance_profile,
  # the account's SCP rejects custom IAM resource creation.
  iam_instance_profile = "LabInstanceProfile"

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    async_database_url          = var.async_database_url
    django_events_url           = var.django_events_url
    order_service_shared_secret = var.order_service_shared_secret
  })

  tags = {
    Name = "${var.project_name}-order-service"
  }
}
