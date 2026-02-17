# ---------------------------------------------------------------------------
# Project configuration variables
# ---------------------------------------------------------------------------

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "bas-world-chatbot"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}

# ---------------------------------------------------------------------------
# LocalStack configuration
# ---------------------------------------------------------------------------

variable "use_localstack" {
  description = "Use LocalStack for local development (set to false for real AWS)"
  type        = bool
  default     = true
}

variable "localstack_endpoint" {
  description = "LocalStack endpoint URL"
  type        = string
  default     = "http://localhost:4566"
}

# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------

variable "api_port" {
  description = "Port the API container listens on"
  type        = number
  default     = 8000
}

variable "openrouter_model" {
  description = "OpenRouter LLM model identifier"
  type        = string
  default     = "google/gemini-2.5-flash"
}

variable "task_cpu" {
  description = "CPU units for ECS Fargate task (1024 = 1 vCPU)"
  type        = string
  default     = "512"
}

variable "task_memory" {
  description = "Memory (MiB) for ECS Fargate task"
  type        = string
  default     = "1024"
}
