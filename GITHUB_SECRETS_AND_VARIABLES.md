# GitHub Secrets and Variables for CI/CD

This document lists all the GitHub Secrets and Variables you need to configure in your repository settings for the CI/CD workflows to work.

## 🔐 Required Secrets

These are sensitive values that should be stored as **Secrets** in GitHub:

### AWS Credentials
- **`AWS_ACCESS_KEY_ID`** - AWS access key ID for CI/CD operations
- **`AWS_SECRET_ACCESS_KEY`** - AWS secret access key for CI/CD operations

> **Note**: These credentials need permissions for:
> - ECR (Elastic Container Registry) - push/pull images
> - ECS (Elastic Container Service) - deploy services
> - Terraform operations (for infra workflow) - create/modify AWS resources

---

## 📋 Required Variables

These are non-sensitive configuration values that should be stored as **Variables** in GitHub:

### AWS Configuration
- **`AWS_REGION`** - AWS region where resources are deployed (e.g., `ap-northeast-3`, `us-east-1`)
- **`AWS_ACCOUNT_ID`** - Your AWS account ID (12-digit number)

### ECS Configuration
- **`ECS_CLUSTER`** - Name of your ECS cluster (e.g., `pdf-knowledge-assistant-cluster`)

### ECR Configuration
- **`ECR_REPO`** - Base ECR repository name (used as fallback if specific repos not set)
  - Example: `pdf-knowledge-assistant`

---

## 🔧 Optional Variables (with defaults)

These variables have default values in the workflows but can be customized:

### ECR Repository Names
- **`ECR_REPO_API`** - ECR repository name for API (defaults to `ECR_REPO` or `pdf-knowledge-assistant-api`)
- **`ECR_REPO_UI`** - ECR repository name for UI (defaults to `ECR_REPO` or `pdf-knowledge-assistant-ui`)

### ECS Service Names
- **`ECS_SERVICE`** - Base ECS service name (used in infra workflow)
- **`ECS_SERVICE_API`** - ECS service name for API (defaults to `pdf-knowledge-assistant-svc-api`)
- **`ECS_SERVICE_UI`** - ECS service name for UI (defaults to `pdf-knowledge-assistant-svc-ui`)

### ECS Container Names
- **`ECS_CONTAINER_NAME_API`** - Container name in API task definition (defaults to `pdf-knowledge-assistant-api`)
- **`ECS_CONTAINER_NAME_UI`** - Container name in UI task definition (defaults to `pdf-knowledge-assistant-ui`)

---

## 📝 Application Secrets (AWS Secrets Manager)

**Important**: The following secrets are NOT stored in GitHub but must be configured in **AWS Secrets Manager**. The task definitions reference them:

- **`DB_PASSWORD`** - Database password
- **`JWT_SECRET_KEY`** - JWT signing secret
- **`OPENAI_API_KEY`** - OpenAI API key
- **`PINECONE_API_KEY`** - Pinecone API key

These should be stored in AWS Secrets Manager with the secret name: `pdf-knowledge-assistant-secrets`

The ARN format used in task definitions:
```
arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:pdf-knowledge-assistant-secrets-{SUFFIX}:{KEY}::
```

---

## 🚀 How to Set Up

### In GitHub Repository:

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**

2. **Add Secrets** (click "New repository secret"):
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

3. **Add Variables** (click "New repository variable"):
   - `AWS_REGION`
   - `AWS_ACCOUNT_ID`
   - `ECS_CLUSTER`
   - `ECR_REPO` (or set `ECR_REPO_API` and `ECR_REPO_UI` separately)

4. **Optional Variables** (only if you want to override defaults):
   - `ECR_REPO_API`
   - `ECR_REPO_UI`
   - `ECS_SERVICE_API`
   - `ECS_SERVICE_UI`
   - `ECS_CONTAINER_NAME_API`
   - `ECS_CONTAINER_NAME_UI`

### In AWS Secrets Manager:

1. Create a secret named `pdf-knowledge-assistant-secrets` in your AWS region
2. Store the following key-value pairs:
   - `DB_PASSWORD`: Your database password
   - `JWT_SECRET_KEY`: A secure random string for JWT signing
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `PINECONE_API_KEY`: Your Pinecone API key

---

## ✅ Quick Checklist

- [ ] `AWS_ACCESS_KEY_ID` (Secret)
- [ ] `AWS_SECRET_ACCESS_KEY` (Secret)
- [ ] `AWS_REGION` (Variable)
- [ ] `AWS_ACCOUNT_ID` (Variable)
- [ ] `ECS_CLUSTER` (Variable)
- [ ] `ECR_REPO` (Variable) or `ECR_REPO_API` + `ECR_REPO_UI`
- [ ] AWS Secrets Manager secret: `pdf-knowledge-assistant-secrets` with all 4 keys

---

## 🔍 Workflow Files Reference

- **API Workflow**: `.github/workflows/api.yml`
- **UI Workflow**: `.github/workflows/ui.yml`
- **Infrastructure Workflow**: `.github/workflows/infra.yml`
