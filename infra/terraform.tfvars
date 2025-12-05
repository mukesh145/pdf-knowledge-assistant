# AWS Configuration
region = "us-east-1"  # TODO: Set your AWS region

# Application Configuration
app_name = "pdf-knowledge-assistant"  # TODO: Update with your application name

# VPC Configuration
vpc_cidr = "10.0.0.0/16"  # TODO: Adjust if needed (must be /16 for 4 subnets)

# Networking Configuration
enable_nat_gateway        = true   # Set to false to disable NAT gateways (saves costs but private subnets won't have internet access)
ecs_use_private_subnets   = false  # Set to true to deploy ECS tasks in private subnets

# Container Configuration
container_port    = 8000  # TODO: Set your container port (used for UI if ui_port not set)
health_check_path = "/health"  # TODO: Set your health check endpoint (used for UI if ui_health_check_path not set)

# UI Configuration
ui_port              = null  # TODO: Set UI port if different from container_port (null = use container_port)
ui_health_check_path = null  # TODO: Set UI health check path if different (null = use health_check_path)

# API Configuration
api_port              = 8000  # TODO: Set your API container port
api_health_check_path = "/api/health"  # TODO: Set your API health check endpoint

# RDS Configuration
rds_port              = 5432  # TODO: Set your RDS database port (default: 5432 for PostgreSQL, 3306 for MySQL)
rds_instance_class    = "db.t3.micro"  # TODO: Set RDS instance class (e.g., db.t3.micro, db.t3.small, db.t3.medium)
rds_allocated_storage = 20  # TODO: Set initial storage in GB
rds_max_allocated_storage = 100  # TODO: Set maximum storage for autoscaling in GB
rds_engine            = "postgres"  # TODO: Database engine (postgres, mysql, etc.)
rds_engine_version    = "15.4"  # TODO: Database engine version
rds_database_name     = "pdf_knowledge_db"  # TODO: Set your database name
rds_username          = "admin"  # TODO: Set RDS master username
rds_password          = "CHANGE_ME_PASSWORD"  # TODO: Set a strong RDS master password
rds_backup_retention_period = 7  # TODO: Set backup retention period in days
rds_backup_window     = "03:00-04:00"  # TODO: Set backup window (UTC)
rds_maintenance_window = "mon:04:00-mon:05:00"  # TODO: Set maintenance window (UTC)
rds_multi_az         = false  # TODO: Set to true for high availability (increases cost)
rds_publicly_accessible = false  # Should be false for private subnet deployment
rds_skip_final_snapshot = false  # Set to true to skip final snapshot on deletion (not recommended for production)
rds_deletion_protection = true  # Enable deletion protection for RDS instance (recommended for production)

# ECS Task Configuration (defaults - used if UI/API specific values not set)
task_cpu    = 512   # TODO: Adjust based on your needs (1024 = 1 vCPU)
task_memory = 1024  # TODO: Adjust based on your needs (in MB)
ephemeral_storage = 21  # Ephemeral storage in GiB

# UI Task Configuration
ui_task_cpu    = null  # TODO: Set UI task CPU if different from task_cpu (null = use task_cpu)
ui_task_memory = null  # TODO: Set UI task memory if different from task_memory (null = use task_memory)

# API Task Configuration
api_task_cpu    = null  # TODO: Set API task CPU if different from task_cpu (null = use task_cpu)
api_task_memory = null  # TODO: Set API task memory if different from task_memory (null = use task_memory)

# Docker Images
image_uri    = "YOUR_ECR_REPO_URI:latest"  # TODO: Set your ECR image URI (used for UI if ui_image_uri not set)
ui_image_uri = null  # TODO: Set UI image URI if different from image_uri (null = use image_uri)
api_image_uri = null  # TODO: Set API image URI if different from image_uri (null = use image_uri)

# ECS Service Configuration (defaults - used if UI/API specific values not set)
desired_count = 1  # TODO: Set desired number of tasks

# UI Service Configuration
ui_desired_count = null  # TODO: Set UI desired count if different from desired_count (null = use desired_count)

# API Service Configuration
api_desired_count = null  # TODO: Set API desired count if different from desired_count (null = use desired_count)

# CloudWatch Logs
log_retention_days = 7  # TODO: Adjust log retention period

# ECS CPU Architecture
ecs_cpu_architecture = "ARM64"  # CPU architecture for ECS tasks (ARM64 or X86_64)

# S3 Configuration
s3_bucket_name = "knowledge-assistant-project"  # S3 bucket name for application data storage (set to null to disable S3 permissions)

# Backend API Environment Variables
# Note: DB credentials will use RDS values if not specified here
db_host = null  # Will use RDS endpoint automatically if null
db_name = null  # Will use rds_database_name if null
db_user = null  # Will use rds_username if null
db_password = null  # Will use rds_password if null

jwt_secret_key = "CHANGE_ME_JWT_SECRET_KEY"  # TODO: Set a strong JWT secret key
openai_api_key = "CHANGE_ME_OPENAI_API_KEY"  # TODO: Set your OpenAI API key
pinecone_api_key = "CHANGE_ME_PINECONE_API_KEY"  # TODO: Set your Pinecone API key
pinecone_index_name = "test"  # TODO: Set your Pinecone index name
pinecone_environment = "us-east-1"  # TODO: Set your Pinecone environment/region

# CORS Configuration
allowed_origins = null  # Will use ALB URL automatically if null (comma-separated for multiple origins)

# Frontend Configuration
api_base_url = null  # Will use ALB URL automatically if null

