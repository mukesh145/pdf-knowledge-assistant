terraform{
    required_version = ">= 1.6.0"
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~>5.60"
        }
    }
}


provider "aws" {
    region = var.region
}

# Get availability zones in the region
data "aws_availability_zones" "available" {
    state = "available"
}

# VPC
resource "aws_vpc" "main" {
    cidr_block           = var.vpc_cidr
    enable_dns_hostnames = true
    enable_dns_support   = true

    tags = {
        Name = "${var.app_name}-vpc"
    }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
    vpc_id = aws_vpc.main.id

    tags = {
        Name = "${var.app_name}-igw"
    }
}

# Public Subnets
resource "aws_subnet" "public" {
    count                   = 2
    vpc_id                  = aws_vpc.main.id
    cidr_block              = cidrsubnet(var.vpc_cidr, 2, count.index)
    availability_zone       = data.aws_availability_zones.available.names[count.index]
    map_public_ip_on_launch = true

    tags = {
        Name = "${var.app_name}-public-subnet-${count.index + 1}"
        Type = "public"
    }
}

# Private Subnets
resource "aws_subnet" "private" {
    count             = 2
    vpc_id            = aws_vpc.main.id
    cidr_block        = cidrsubnet(var.vpc_cidr, 2, count.index + 2)
    availability_zone = data.aws_availability_zones.available.names[count.index]

    tags = {
        Name = "${var.app_name}-private-subnet-${count.index + 1}"
        Type = "private"
    }
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
    count  = var.enable_nat_gateway ? 2 : 0
    domain = "vpc"

    tags = {
        Name = "${var.app_name}-nat-eip-${count.index + 1}"
    }

    depends_on = [aws_internet_gateway.main]
}



# NAT Gateways
resource "aws_nat_gateway" "main" {
    count         = var.enable_nat_gateway ? 2 : 0
    allocation_id = aws_eip.nat[count.index].id
    subnet_id     = aws_subnet.public[count.index].id

    tags = {
        Name = "${var.app_name}-nat-gateway-${count.index + 1}"
    }

    depends_on = [aws_internet_gateway.main]
}



# Route Table for Public Subnets
resource "aws_route_table" "public" {
    vpc_id = aws_vpc.main.id

    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.main.id
    }

    tags = {
        Name = "${var.app_name}-public-rt"
    }
}

# Route Table Associations for Public Subnets
resource "aws_route_table_association" "public" {
    count          = 2
    subnet_id      = aws_subnet.public[count.index].id
    route_table_id = aws_route_table.public.id
}

# Route Tables for Private Subnets
resource "aws_route_table" "private" {
    count  = 2  # Always create, regardless of NAT gateway
    vpc_id = aws_vpc.main.id

    dynamic "route" {
        for_each = var.enable_nat_gateway ? [1] : []
        content {
            cidr_block     = "0.0.0.0/0"
            nat_gateway_id = aws_nat_gateway.main[count.index].id
        }
    }

    tags = {
        Name = "${var.app_name}-private-rt-${count.index + 1}"
    }
}

# Route Table Associations for Private Subnets
resource "aws_route_table_association" "private" {
    count          = 2  # Always associate
    subnet_id      = aws_subnet.private[count.index].id
    route_table_id = aws_route_table.private[count.index].id
}

locals{
    public_subnets  = aws_subnet.public[*].id
    private_subnets = aws_subnet.private[*].id
    alb_subnets     = aws_subnet.public[*].id
    ecs_subnets     = var.ecs_use_private_subnets ? aws_subnet.private[*].id : aws_subnet.public[*].id
    app_name        = var.app_name
    log_group_name  = "/ecs/${var.app_name}"
    container_port  = var.container_port
    
    # Environment variables
    db_host          = var.db_host != null ? var.db_host : aws_db_instance.main.endpoint
    db_name          = var.db_name != null ? var.db_name : var.rds_database_name
    db_user          = var.db_user != null ? var.db_user : var.rds_username
    db_password      = var.db_password != null ? var.db_password : var.rds_password
    alb_dns_name     = aws_lb.this.dns_name
    alb_url          = "http://${aws_lb.this.dns_name}"
    allowed_origins  = var.allowed_origins != null ? var.allowed_origins : local.alb_url
    api_base_url     = var.api_base_url != null ? var.api_base_url : local.alb_url
}



#---Security groups ----
# 1. ALB Security Group - accepts public traffic from anywhere and routes to the listener
resource "aws_security_group" "alb_sg" {
    name_prefix = "${var.app_name}-alb-sg-"
    description = "ALB security group - accepts public traffic from anywhere"
    vpc_id      = aws_vpc.main.id

    ingress {
        description      = "HTTP from anywhere"
        from_port        = 80
        to_port          = 80
        protocol         = "tcp"
        cidr_blocks      = ["0.0.0.0/0"]
        ipv6_cidr_blocks = ["::/0"]
    }

    egress {
        description      = "Allow all outbound traffic"
        from_port        = 0
        to_port          = 0
        protocol         = "-1"
        cidr_blocks      = ["0.0.0.0/0"]
        ipv6_cidr_blocks = ["::/0"]
    }

    tags = {
        Name = "${var.app_name}-alb-sg"
    }
}

# 2. ECS Security Group - accepts requests only from ALB and can send to anyone
resource "aws_security_group" "ecs_sg" {
    name_prefix = "${var.app_name}-ecs-sg-"
    description = "Security group for ECS tasks - accepts requests only from ALB"
    vpc_id      = aws_vpc.main.id

    ingress {
        description     = "From ALB only - UI port"
        from_port       = var.ui_port != null ? var.ui_port : var.container_port
        to_port         = var.ui_port != null ? var.ui_port : var.container_port
        protocol        = "tcp"
        security_groups = [aws_security_group.alb_sg.id]
    }

    ingress {
        description     = "From ALB only - API port"
        from_port       = var.api_port
        to_port         = var.api_port
        protocol        = "tcp"
        security_groups = [aws_security_group.alb_sg.id]
    }

    egress {
        description      = "Allow all outbound traffic"
        from_port        = 0
        to_port          = 0
        protocol         = "-1"
        cidr_blocks      = ["0.0.0.0/0"]
        ipv6_cidr_blocks = ["::/0"]
    }

    tags = {
        Name = "${var.app_name}-ecs-sg"
    }
}

# 3. RDS Security Group - accepts only from ECS security group
resource "aws_security_group" "rds_sg" {
    name_prefix = "${var.app_name}-rds-sg-"
    description = "Security group for RDS - accepts only from ECS"
    vpc_id      = aws_vpc.main.id

    ingress {
        description     = "From ECS only"
        from_port       = var.rds_port
        to_port         = var.rds_port
        protocol        = "tcp"
        security_groups = [aws_security_group.ecs_sg.id]
    }

    egress {
        description      = "Allow all outbound traffic"
        from_port        = 0
        to_port          = 0
        protocol         = "-1"
        cidr_blocks      = ["0.0.0.0/0"]
        ipv6_cidr_blocks = ["::/0"]
    }

    tags = {
        Name = "${var.app_name}-rds-sg"
    }
}

# ----RDS Database ----
# RDS Subnet Group - uses private subnets
resource "aws_db_subnet_group" "main" {
    name       = "${var.app_name}-db-subnet-group"
    subnet_ids = aws_subnet.private[*].id

    tags = {
        Name = "${var.app_name}-db-subnet-group"
    }
}

# RDS Parameter Group (optional - for custom PostgreSQL settings)
resource "aws_db_parameter_group" "main" {
    family = "${var.rds_engine}${split(".", var.rds_engine_version)[0]}"
    name   = "${var.app_name}-db-params"

    tags = {
        Name = "${var.app_name}-db-params"
    }
}

# RDS Instance - deployed in private subnets
resource "aws_db_instance" "main" {
    identifier             = "${var.app_name}-db"
    engine                 = var.rds_engine
    engine_version         = var.rds_engine_version
    instance_class         = var.rds_instance_class
    allocated_storage      = var.rds_allocated_storage
    max_allocated_storage  = var.rds_max_allocated_storage
    storage_type           = "gp3"
    storage_encrypted       = true

    db_name  = var.rds_database_name
    username = var.rds_username
    password = var.rds_password
    port     = var.rds_port

    db_subnet_group_name   = aws_db_subnet_group.main.name
    parameter_group_name   = aws_db_parameter_group.main.name
    vpc_security_group_ids = [aws_security_group.rds_sg.id]

    publicly_accessible = var.rds_publicly_accessible
    multi_az            = var.rds_multi_az

    backup_retention_period = var.rds_backup_retention_period
    backup_window          = var.rds_backup_window
    maintenance_window     = var.rds_maintenance_window

    skip_final_snapshot       = var.rds_skip_final_snapshot
    final_snapshot_identifier = var.rds_skip_final_snapshot ? null : "${var.app_name}-db-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
    deletion_protection       = var.rds_deletion_protection

    enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

    performance_insights_enabled = false

    tags = {
        Name = "${var.app_name}-db"
    }
}

# ----Load Balancer + TG + Listener ------

# Application Load Balancer - placed in both public subnets
resource "aws_lb" "this" {
    name               = "${var.app_name}-alb"
    internal           = false
    load_balancer_type = "application"
    security_groups    = [aws_security_group.alb_sg.id]
    subnets            = local.alb_subnets  # Both public subnets

    enable_deletion_protection = false

    tags = {
        Name = "${var.app_name}-alb"
    }
}

# Target Group 1 - UI (routes /)
resource "aws_lb_target_group" "ui" {
    name     = "${var.app_name}-tg-ui"
    port     = var.ui_port != null ? var.ui_port : var.container_port
    protocol = "HTTP"
    vpc_id   = aws_vpc.main.id
    target_type = "ip"

    health_check {
        path                = var.ui_health_check_path != null ? var.ui_health_check_path : var.health_check_path
        healthy_threshold   = 2
        unhealthy_threshold = 3
        timeout             = 5
        interval            = 15
        matcher             = "200-399"
    }

    tags = {
        Name = "${var.app_name}-tg-ui"
    }
}

# Target Group 2 - API (routes /api)
resource "aws_lb_target_group" "api" {
    name     = "${var.app_name}-tg-api"
    port     = var.api_port
    protocol = "HTTP"
    vpc_id   = aws_vpc.main.id
    target_type = "ip"

    health_check {
        path                = var.api_health_check_path
        healthy_threshold   = 2
        unhealthy_threshold = 3
        timeout             = 5
        interval            = 15
        matcher             = "200-399"
    }

    tags = {
        Name = "${var.app_name}-tg-api"
    }
}

# Listener with path-based routing
resource "aws_lb_listener" "http" {
    load_balancer_arn = aws_lb.this.arn
    port              = 80
    protocol          = "HTTP"

    # Default action: route / to UI target group
    default_action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.ui.arn
    }
}

# Listener rule for /api path - routes to API target group
# Lower priority number = evaluated first (priority 1 = highest priority)
resource "aws_lb_listener_rule" "api" {
    listener_arn = aws_lb_listener.http.arn
    priority     = 1

    action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.api.arn
    }

    condition {
        path_pattern {
            values = ["/api*"]
        }
    }
}


#-----CloudWatch Logs------
resource "aws_cloudwatch_log_group" "ecs_ui" {
    name              = "${local.log_group_name}-ui"
    retention_in_days = var.log_retention_days

    tags = {
        Name = "${var.app_name}-logs-ui"
    }
}

resource "aws_cloudwatch_log_group" "ecs_api" {
    name              = "${local.log_group_name}-api"
    retention_in_days = var.log_retention_days

    tags = {
        Name = "${var.app_name}-logs-api"
    }
}



#------IAM---------
data "aws_iam_policy_document" "task_exec_assume" {
    statement {
        actions = ["sts:AssumeRole"]
        principals {
            type = "Service"
            identifiers = ["ecs-tasks.amazonaws.com"]
        }
    }
}

resource "aws_iam_role" "task_exec"{
    name = "${var.app_name}-exec-role"
    assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json
}

resource "aws_iam_role_policy_attachment" "exec_attach"{
    role = aws_iam_role.task_exec.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM policy for ECR access
data "aws_iam_policy_document" "ecr_access" {
    statement {
        actions = [
            "ecr:GetAuthorizationToken",
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage"
        ]
        resources = ["*"]
    }
}

resource "aws_iam_role_policy" "ecr_access" {
    name   = "${var.app_name}-ecr-access"
    role   = aws_iam_role.task_exec.id
    policy = data.aws_iam_policy_document.ecr_access.json
}

# IAM Task Role - for application permissions (accessing AWS services from containers)
resource "aws_iam_role" "task_role" {
    name = "${var.app_name}-task-role"
    assume_role_policy = data.aws_iam_policy_document.task_exec_assume.json

    tags = {
        Name = "${var.app_name}-task-role"
    }
}

#--------ECR Repository-----------
# Note: ECR repositories are created manually through AWS Console
# Using data sources to reference existing repositories
data "aws_ecr_repository" "api" {
    name = var.ecr_repo_api_name != null ? var.ecr_repo_api_name : "${var.app_name}-api"
}

data "aws_ecr_repository" "ui" {
    name = var.ecr_repo_ui_name != null ? var.ecr_repo_ui_name : "${var.app_name}-ui"
}

#--------ECS Cluster-----------

resource "aws_ecs_cluster" "this" {
    name = "${var.app_name}-cluster"

    tags = {
        Name = "${var.app_name}-cluster"
    }
}

# Task Definition for UI
resource "aws_ecs_task_definition" "ui" {
    family                   = "${var.app_name}-td-ui"
    requires_compatibilities  = ["FARGATE"]
    network_mode             = "awsvpc"
    cpu                      = var.ui_task_cpu != null ? var.ui_task_cpu : var.task_cpu
    memory                   = var.ui_task_memory != null ? var.ui_task_memory : var.task_memory
    execution_role_arn       = aws_iam_role.task_exec.arn
    task_role_arn            = aws_iam_role.task_role.arn

    runtime_platform {
        operating_system_family = "LINUX"
        cpu_architecture        = var.ecs_cpu_architecture
    }

    ephemeral_storage {
        size_in_gib = var.ephemeral_storage
    }

    container_definitions = jsonencode([
        {
            name      = "${var.app_name}-ui"
            image     = var.ui_image_uri != null ? var.ui_image_uri : var.image_uri
            essential = true
            portMappings = [{
                containerPort = var.ui_port != null ? var.ui_port : var.container_port
                protocol      = "tcp"
            }]
            environment = [
                {
                    name  = "VITE_API_BASE_URL"
                    value = local.api_base_url
                }
            ]
            logConfiguration = {
                logDriver = "awslogs"
                options = {
                    "awslogs-group"         = "${local.log_group_name}-ui"
                    "awslogs-region"        = var.region
                    "awslogs-stream-prefix" = "${var.app_name}-ui"
                }
            }
            healthCheck = {
                command     = ["CMD-SHELL", "curl -sf http://localhost:${var.ui_port != null ? var.ui_port : var.container_port}${var.ui_health_check_path != null ? var.ui_health_check_path : var.health_check_path} || exit 1"]
                interval    = 15
                timeout     = 5
                retries     = 3
                startPeriod = 10
            }
        }
    ])

    tags = {
        Name = "${var.app_name}-td-ui"
    }
}

# Task Definition for API
resource "aws_ecs_task_definition" "api" {
    family                   = "${var.app_name}-td-api"
    requires_compatibilities  = ["FARGATE"]
    network_mode             = "awsvpc"
    cpu                      = var.api_task_cpu != null ? var.api_task_cpu : var.task_cpu
    memory                   = var.api_task_memory != null ? var.api_task_memory : var.task_memory
    execution_role_arn       = aws_iam_role.task_exec.arn
    task_role_arn            = aws_iam_role.task_role.arn

    runtime_platform {
        operating_system_family = "LINUX"
        cpu_architecture        = var.ecs_cpu_architecture
    }

    ephemeral_storage {
        size_in_gib = var.ephemeral_storage
    }

    container_definitions = jsonencode([
        {
            name      = "${var.app_name}-api"
            image     = var.api_image_uri != null ? var.api_image_uri : var.image_uri
            essential = true
            portMappings = [{
                containerPort = var.api_port
                protocol      = "tcp"
            }]
            environment = [
                {
                    name  = "DB_HOST"
                    value = local.db_host
                },
                {
                    name  = "DB_NAME"
                    value = local.db_name
                },
                {
                    name  = "DB_USER"
                    value = local.db_user
                },
                {
                    name  = "DB_PASSWORD"
                    value = local.db_password
                },
                {
                    name  = "JWT_SECRET_KEY"
                    value = var.jwt_secret_key
                },
                {
                    name  = "OPENAI_API_KEY"
                    value = var.openai_api_key
                },
                {
                    name  = "PINECONE_API_KEY"
                    value = var.pinecone_api_key
                },
                {
                    name  = "PINECONE_INDEX_NAME"
                    value = var.pinecone_index_name
                },
                {
                    name  = "PINECONE_ENVIRONMENT"
                    value = var.pinecone_environment
                },
                {
                    name  = "ALLOWED_ORIGINS"
                    value = local.allowed_origins
                }
            ]
            logConfiguration = {
                logDriver = "awslogs"
                options = {
                    "awslogs-group"         = "${local.log_group_name}-api"
                    "awslogs-region"        = var.region
                    "awslogs-stream-prefix" = "${var.app_name}-api"
                }
            }
            healthCheck = {
                command     = ["CMD-SHELL", "curl -sf http://localhost:${var.api_port}${var.api_health_check_path} || exit 1"]
                interval    = 15
                timeout     = 5
                retries     = 3
                startPeriod = 10
            }
        }
    ])

    tags = {
        Name = "${var.app_name}-td-api"
    }
}

# ECS Service for UI
resource "aws_ecs_service" "ui" {
    name            = "${var.app_name}-svc-ui"
    cluster         = aws_ecs_cluster.this.id
    task_definition = aws_ecs_task_definition.ui.arn
    desired_count   = var.ui_desired_count != null ? var.ui_desired_count : var.desired_count
    launch_type     = "FARGATE"
    force_new_deployment = true

    network_configuration {
        subnets         = local.ecs_subnets
        security_groups = [aws_security_group.ecs_sg.id]
        assign_public_ip = var.ecs_use_private_subnets ? false : true
    }

    # Register with UI target group (tg-ui)
    load_balancer {
        target_group_arn = aws_lb_target_group.ui.arn
        container_name   = "${var.app_name}-ui"
        container_port   = var.ui_port != null ? var.ui_port : var.container_port
    }

    lifecycle {
        ignore_changes = [desired_count]
    }

    depends_on = [aws_lb_listener.http]

    tags = {
        Name = "${var.app_name}-svc-ui"
    }
}

# ECS Service for API
resource "aws_ecs_service" "api" {
    name            = "${var.app_name}-svc-api"
    cluster         = aws_ecs_cluster.this.id
    task_definition = aws_ecs_task_definition.api.arn
    desired_count   = var.api_desired_count != null ? var.api_desired_count : var.desired_count
    launch_type     = "FARGATE"
    force_new_deployment = true

    network_configuration {
        subnets         = local.ecs_subnets
        security_groups = [aws_security_group.ecs_sg.id]
        assign_public_ip = var.ecs_use_private_subnets ? false : true
    }

    # Register with API target group (tg-api)
    load_balancer {
        target_group_arn = aws_lb_target_group.api.arn
        container_name   = "${var.app_name}-api"
        container_port   = var.api_port
    }

    lifecycle {
        ignore_changes = [desired_count]
    }

    depends_on = [aws_lb_listener.http]

    tags = {
        Name = "${var.app_name}-svc-api"
    }
}