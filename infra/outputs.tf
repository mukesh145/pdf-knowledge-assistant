output "vpc_id" {
    description = "VPC ID"
    value       = aws_vpc.main.id
}

output "public_subnet_ids" {
    description = "Public subnet IDs"
    value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
    description = "Private subnet IDs"
    value       = aws_subnet.private[*].id
}

output "ecs_cluster_name" {
    description = "ECS cluster name"
    value       = aws_ecs_cluster.this.name
}

output "ecs_cluster_arn" {
    description = "ECS cluster ARN"
    value       = aws_ecs_cluster.this.arn
}

output "ecs_service_ui_name" {
    description = "ECS service name for UI"
    value       = aws_ecs_service.ui.name
}

output "ecs_service_api_name" {
    description = "ECS service name for API"
    value       = aws_ecs_service.api.name
}

output "alb_dns_name" {
    description = "ALB DNS name"
    value       = aws_lb.this.dns_name
}

output "alb_url" {
    description = "ALB URL"
    value       = "http://${aws_lb.this.dns_name}"
}

output "ecr_repository_api_url" {
    description = "ECR repository URL for API"
    value       = data.aws_ecr_repository.api.repository_url
}

output "ecr_repository_api_name" {
    description = "ECR repository name for API"
    value       = data.aws_ecr_repository.api.name
}

output "ecr_repository_ui_url" {
    description = "ECR repository URL for UI"
    value       = data.aws_ecr_repository.ui.repository_url
}

output "ecr_repository_ui_name" {
    description = "ECR repository name for UI"
    value       = data.aws_ecr_repository.ui.name
}

output "rds_endpoint" {
    description = "RDS instance endpoint"
    value       = aws_db_instance.main.endpoint
    sensitive   = true
}

output "rds_database_name" {
    description = "RDS database name"
    value       = aws_db_instance.main.db_name
}

output "task_execution_role_arn" {
    description = "ECS task execution role ARN"
    value       = aws_iam_role.task_exec.arn
}

output "task_role_arn" {
    description = "ECS task role ARN"
    value       = aws_iam_role.task_role.arn
}

output "ui_target_group_arn" {
    description = "UI target group ARN"
    value       = aws_lb_target_group.ui.arn
}

output "api_target_group_arn" {
    description = "API target group ARN"
    value       = aws_lb_target_group.api.arn
}

