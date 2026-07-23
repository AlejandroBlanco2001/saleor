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

resource "aws_instance" "order_service" {
  ami                    = data.aws_ami.base.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
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
