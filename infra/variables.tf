variable "region" {
    description = "AWS region where resources will be created"
    type        = string
}

variable "app_name" {
    description = "Application name used for resource naming"
    type        = string
}

variable "vpc_cidr" {
    description = "CIDR block for the VPC"
    type        = string
    default     = "10.0.0.0/16"
}

variable "enable_nat_gateway" {
    description = "Enable NAT Gateway for private subnets"
    type        = bool
    default     = true
}

variable "ecs_use_private_subnets" {
    description = "Whether to deploy ECS tasks in private subnets"
    type        = bool
    default     = false
}

variable "container_port" {
    description = "Port on which the container listens (used for UI)"
    type        = number
}

variable "ui_port" {
    description = "Port on which the UI container listens"
    type        = number
    default     = null  # If not set, uses container_port
}

variable "api_port" {
    description = "Port on which the API container listens"
    type        = number
}

variable "rds_port" {
    description = "Port on which RDS database listens"
    type        = number
    default     = 5432
}

variable "health_check_path" {
    description = "Health check path for the load balancer (used for UI)"
    type        = string
}

variable "ui_health_check_path" {
    description = "Health check path for UI target group"
    type        = string
    default     = null  # If not set, uses health_check_path
}

variable "api_health_check_path" {
    description = "Health check path for API target group"
    type        = string
}

variable "log_retention_days" {
    description = "CloudWatch log retention in days"
    type        = number
    default     = 7
}

variable "task_cpu" {
    description = "CPU units for ECS task (1024 = 1 vCPU) - used for UI if ui_task_cpu not set"
    type        = number
}

variable "task_memory" {
    description = "Memory for ECS task in MB - used for UI if ui_task_memory not set"
    type        = number
}

variable "ui_task_cpu" {
    description = "CPU units for UI ECS task (1024 = 1 vCPU)"
    type        = number
    default     = null  # If not set, uses task_cpu
}

variable "ui_task_memory" {
    description = "Memory for UI ECS task in MB"
    type        = number
    default     = null  # If not set, uses task_memory
}

variable "api_task_cpu" {
    description = "CPU units for API ECS task (1024 = 1 vCPU)"
    type        = number
    default     = null  # If not set, uses task_cpu
}

variable "api_task_memory" {
    description = "Memory for API ECS task in MB"
    type        = number
    default     = null  # If not set, uses task_memory
}

variable "ephemeral_storage" {
    description = "Ephemeral storage size in GiB for ECS task"
    type        = number
    default     = 21
}

variable "image_uri" {
    description = "Docker image URI for the ECS task (used for UI if ui_image_uri not set)"
    type        = string
}

variable "ui_image_uri" {
    description = "Docker image URI for UI container"
    type        = string
    default     = null  # If not set, uses image_uri
}

variable "api_image_uri" {
    description = "Docker image URI for API container"
    type        = string
    default     = null  # If not set, uses image_uri
}

variable "desired_count" {
    description = "Desired number of ECS tasks (used for UI if ui_desired_count not set)"
    type        = number
    default     = 1
}

variable "ui_desired_count" {
    description = "Desired number of UI ECS tasks"
    type        = number
    default     = null  # If not set, uses desired_count
}

variable "api_desired_count" {
    description = "Desired number of API ECS tasks"
    type        = number
    default     = null  # If not set, uses desired_count
}

# RDS Configuration
variable "rds_instance_class" {
    description = "RDS instance class (e.g., db.t3.micro, db.t3.small)"
    type        = string
    default     = "db.t3.micro"
}

variable "rds_allocated_storage" {
    description = "RDS allocated storage in GB"
    type        = number
    default     = 20
}

variable "rds_max_allocated_storage" {
    description = "RDS maximum allocated storage for autoscaling in GB"
    type        = number
    default     = 100
}

variable "rds_engine" {
    description = "RDS database engine"
    type        = string
    default     = "postgres"
}

variable "rds_engine_version" {
    description = "RDS database engine version"
    type        = string
    default     = "15.4"
}

variable "rds_database_name" {
    description = "RDS database name"
    type        = string
}

variable "rds_username" {
    description = "RDS master username"
    type        = string
    sensitive   = true
}

variable "rds_password" {
    description = "RDS master password"
    type        = string
    sensitive   = true
}

variable "rds_backup_retention_period" {
    description = "RDS backup retention period in days"
    type        = number
    default     = 7
}

variable "rds_backup_window" {
    description = "RDS backup window (e.g., '03:00-04:00')"
    type        = string
    default     = "03:00-04:00"
}

variable "rds_maintenance_window" {
    description = "RDS maintenance window (e.g., 'mon:04:00-mon:05:00')"
    type        = string
    default     = "mon:04:00-mon:05:00"
}

variable "rds_multi_az" {
    description = "Enable RDS Multi-AZ deployment"
    type        = bool
    default     = false
}

variable "rds_publicly_accessible" {
    description = "Make RDS publicly accessible (should be false for private subnet)"
    type        = bool
    default     = false
}

variable "rds_skip_final_snapshot" {
    description = "Skip final snapshot when deleting RDS instance"
    type        = bool
    default     = false
}

variable "rds_deletion_protection" {
    description = "Enable deletion protection for RDS instance"
    type        = bool
    default     = true
}

variable "ecs_cpu_architecture" {
    description = "CPU architecture for ECS tasks (ARM64 or X86_64)"
    type        = string
    default     = "ARM64"
    validation {
        condition     = contains(["ARM64", "X86_64"], var.ecs_cpu_architecture)
        error_message = "CPU architecture must be ARM64 or X86_64"
    }
}

variable "s3_bucket_name" {
    description = "S3 bucket name for application data storage"
    type        = string
    default     = null  # If not set, S3 permissions won't be granted
}

# Backend API Environment Variables
variable "db_host" {
    description = "RDS database host (endpoint) - will use RDS endpoint if not set"
    type        = string
    sensitive   = true
    default     = null
}

variable "db_name" {
    description = "RDS database name - will use rds_database_name if not set"
    type        = string
    default     = null
}

variable "db_user" {
    description = "RDS database username - will use rds_username if not set"
    type        = string
    sensitive   = true
    default     = null
}

variable "db_password" {
    description = "RDS database password - will use rds_password if not set"
    type        = string
    sensitive   = true
    default     = null
}

variable "jwt_secret_key" {
    description = "JWT secret key for token generation"
    type        = string
    sensitive   = true
}

variable "openai_api_key" {
    description = "OpenAI API key"
    type        = string
    sensitive   = true
}

variable "pinecone_api_key" {
    description = "Pinecone API key"
    type        = string
    sensitive   = true
}

variable "pinecone_index_name" {
    description = "Pinecone index name"
    type        = string
    default     = "test"
}

variable "pinecone_environment" {
    description = "Pinecone environment/region"
    type        = string
    default     = "us-east-1"
}

variable "allowed_origins" {
    description = "Comma-separated list of allowed CORS origins (will use ALB URL if not set)"
    type        = string
    default     = null
}

# Frontend Environment Variables
variable "api_base_url" {
    description = "API base URL for frontend (will use ALB URL if not set)"
    type        = string
    default     = null
}

variable "ecr_repo_api_name" {
    description = "ECR repository name for API (will use app_name-api if not set)"
    type        = string
    default     = null
}

variable "ecr_repo_ui_name" {
    description = "ECR repository name for UI (will use app_name-ui if not set)"
    type        = string
    default     = null
}

