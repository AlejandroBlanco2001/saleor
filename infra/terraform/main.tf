terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Default VPC (always present in a Learner Lab account) ---

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# --- Module graph: security -> rds -> order_service, sqs standalone ---
#
#   security  --(order_service_sg_id)-->  order_service
#   security  --(rds_sg_id)------------>  rds  --(endpoint)-->  order_service
#   sqs                                                          (no wiring into AWS resources;
#                                                                  its queue_url only feeds the
#                                                                  root's generated .env.cloud output)

module "security" {
  source = "./modules/security"

  project_name = var.project_name
  vpc_id       = data.aws_vpc.default.id
  my_ip_cidr   = var.my_ip
}

module "rds" {
  source = "./modules/rds"

  project_name      = var.project_name
  security_group_id = module.security.rds_sg_id
  instance_class    = var.db_instance_class
  db_username       = var.db_username
  db_password       = var.db_password
}

module "sqs" {
  source = "./modules/sqs"

  project_name = var.project_name
}

module "order_service" {
  source = "./modules/order_service"

  project_name      = var.project_name
  subnet_id         = data.aws_subnets.default.ids[0]
  security_group_id = module.security.order_service_sg_id
  instance_type     = var.instance_type

  async_database_url          = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${module.rds.endpoint}/saleor"
  django_events_url           = var.django_events_url
  order_service_shared_secret = var.order_service_shared_secret
}
