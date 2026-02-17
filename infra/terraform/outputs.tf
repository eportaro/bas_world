# ---------------------------------------------------------------------------
# Outputs — displayed after terraform apply
# ---------------------------------------------------------------------------

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.chatbot.api_endpoint
}

output "s3_bucket_name" {
  description = "S3 bucket name for inventory data"
  value       = aws_s3_bucket.inventory.id
}

output "ecr_repository_url" {
  description = "ECR repository URL for the chatbot container image"
  value       = aws_ecr_repository.chatbot.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "log_group_name" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.chatbot.name
}
