################################################################################
# BAS World Tractor Head Finder — Terraform Infrastructure
#
# This configuration targets LocalStack for local AWS emulation.
# In production, simply change the provider endpoints to real AWS.
#
# Usage:
#   1. Start LocalStack: docker-compose up -d localstack
#   2. terraform init
#   3. terraform plan
#   4. terraform apply -auto-approve
################################################################################

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# Provider — LocalStack for local dev, real AWS for production
# ---------------------------------------------------------------------------

provider "aws" {
  region                      = var.aws_region
  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  endpoints {
    s3         = var.use_localstack ? var.localstack_endpoint : null
    ecs        = var.use_localstack ? var.localstack_endpoint : null
    ecr        = var.use_localstack ? var.localstack_endpoint : null
    iam        = var.use_localstack ? var.localstack_endpoint : null
    apigateway = var.use_localstack ? var.localstack_endpoint : null
    cloudwatch = var.use_localstack ? var.localstack_endpoint : null
    logs       = var.use_localstack ? var.localstack_endpoint : null
  }
}

# ---------------------------------------------------------------------------
# S3 Bucket — Inventory data storage
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "inventory" {
  bucket        = "${var.project_name}-inventory-${var.environment}"
  force_destroy = true

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_s3_object" "trekkers_csv" {
  bucket = aws_s3_bucket.inventory.id
  key    = "data/trekkers.csv"
  source = "${path.module}/../../data/trekkers.csv"
  etag   = filemd5("${path.module}/../../data/trekkers.csv")
}

# ---------------------------------------------------------------------------
# ECR Repository — Container image registry
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "chatbot" {
  name                 = "${var.project_name}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# IAM — ECS Task execution role
# ---------------------------------------------------------------------------

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ---------------------------------------------------------------------------
# CloudWatch — Log group
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "chatbot" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = 14

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# ECS — Cluster, Task Definition, Service
# ---------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_ecs_task_definition" "chatbot" {
  family                   = "${var.project_name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-api"
      image     = "${aws_ecr_repository.chatbot.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = var.api_port
          hostPort      = var.api_port
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "OPENROUTER_MODEL", value = var.openrouter_model },
        { name = "API_PORT", value = tostring(var.api_port) },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.chatbot.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# API Gateway — Public REST endpoint
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "chatbot" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"
  description   = "BAS World Tractor Head Finder API"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.chatbot.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
