# CI/CD Implementation Plan for Blender Python App

## Overview
This document outlines the plan to implement GitHub Actions CI/CD pipeline for the `combined_blender_app` Python application, deploying to GCP VM instances (development and production environments named "blender").

## Current State Analysis

### Application Stack
- **Type**: Python FastAPI Application
- **Port**: 8000
- **Workers**: 4 (Uvicorn)
- **Container**: Python 3.10-slim with custom dependencies
- **Key Dependencies**: FastAPI, Uvicorn, Boto3, Blender integration
- **Health Endpoint**: `/health`

### Infrastructure Pattern (Based on nest_marketing_web)
The Next.js apps use:
1. **GitHub Actions** for CI/CD (`.github/workflows/ci.yml`)
2. **GCP Artifact Registry** for container storage
3. **VM-based deployment** (not Cloud Run) with Docker
4. **Multi-webapp-server module** in Terraform for orchestration
5. **Dual environments**: Development (fe-dev-467323) and Production (fe-prod-467423)

## Implementation Plan

### Phase 1: GitHub Actions Setup

#### 1.1 Create GitHub Workflow File
**File**: `.github/workflows/ci.yml`

**Key Components**:
```yaml
name: Build and Deploy Blender API (Docker)

on:
  push:
    branches: [ develop, main ]
  pull_request:
    branches: [ develop, main ]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - Checkout code
      - Set up Docker Buildx
      - Determine environment (develop → development, main → production)
      - Build Docker image locally (test)
      - Authenticate to GCP
      - Configure Docker for Artifact Registry
      - Build and Push to GCP Artifact Registry
      - Output deployment info
```

**Environment Mapping**:
- `develop` branch → `development` environment → `fe-dev-467323` project
- `main` branch → `production` environment → `fe-prod-467423` project

**Image Tag Format**:
```
us-central1-docker.pkg.dev/{GCP_PROJECT}/frontend-containers/blender_app:{BUILD_ENV}-latest
```

#### 1.2 GitHub Secrets Required
Create these secrets in GitHub repository settings:

| Secret Name | Description | Environment |
|------------|-------------|-------------|
| `GCP_SA_KEY_FRONTEND_DEV` | GCP Service Account JSON key | Development |
| `GCP_SA_KEY_FRONTEND_PROD` | GCP Service Account JSON key | Production |

**Service Account Email Pattern**:
- Dev: `fe-dev-svc@fe-dev-467323.iam.gserviceaccount.com`
- Prod: `fe-prod-svc@fe-prod-467423.iam.gserviceaccount.com`

### Phase 2: Docker Configuration

#### 2.1 Create CI-Specific Dockerfile
**File**: `ci/Dockerfile`

**Key Differences from Development Dockerfile**:
```dockerfile
FROM python:3.10-slim

# Production optimizations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies (including Blender if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build argument for environment
ARG BUILD_ENV="development"
ENV BUILD_ENV=${BUILD_ENV}

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app
COPY ./app/scripts ./app/scripts

# Create necessary directories
RUN mkdir -p /app/logs /app/working_data

# Expose port
EXPOSE 8000

# Use uvicorn with multiple workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 2.2 Optional: Add PM2 Process Manager (Like Next.js Apps)
For better process management and logging:
```dockerfile
# Install PM2 equivalent for Python (supervisord or circus)
# OR use gunicorn with proper worker management
```

### Phase 3: Infrastructure Setup (Terraform)

#### 3.1 Update Frontend Module Configuration
**Location**: `nest-infra/opentofu/gcp/departments/frontend/development/fe-dev/main.tf`

**Add Blender Application Block**:
```terraform
module "server" {
  source = "../../../frontend/modules/multi-webapp-server"
  
  # ... existing configuration ...
  
  applications = {
    # ... existing apps (next_nest_web, next_marketing_web, etc.) ...
    
    blender_app = {
      container_name = "blender_app_dev"
      # GCP Artifact Registry
      gcp_image_uri  = "us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest"
      ports          = ["8000:8000"]  # External:Internal
      env_vars       = var.blender_app_env_vars
      volumes        = [
        "/var/log/blender-app:/app/logs",
        "/var/blender-working:/app/working_data"
      ]
      health_check_enabled = true
      health_check_path    = "/health"
      cpus                = "2.0"
      mem_limit           = "4096m"  # 4GB for Blender operations
    }
  }
}
```

#### 3.2 Add Variables for Blender App
**Location**: `nest-infra/opentofu/gcp/departments/frontend/development/fe-dev/variables.tf`

```terraform
variable "blender_app_env_vars" {
  description = "Environment variables for Blender API application"
  type        = map(string)
  default     = {
    API_V1_STR                      = "/api/v1"
    PROJECT_NAME                     = "Nestingale Blender API"
    DEBUG                           = "false"
    PORT                            = "8000"
    WORKERS                         = "4"
    AWS_REGION                      = "us-east-1"
    S3_BUCKET_NAME                  = "nestingale-dev-digital-assets"
    S3_PRODUCT_3D_ASSETS_BUCKET     = "nestingale-dev-product-3d-assets"
    BLENDER_SCRIPTS_PATH            = "app/scripts"
    BLENDER_OUTPUT_PATH             = "app/scripts/generated_files"
    BLENDER_PATH                    = "/usr/local/bin/blender"
    LOG_LEVEL                       = "INFO"
    RATE_LIMIT_PER_MINUTE          = "60"
    REQUEST_TIMEOUT                 = "3600"
  }
}
```

#### 3.3 Production Configuration
**Location**: `nest-infra/opentofu/gcp/departments/frontend/production/fe-prod/main.tf`

Mirror the development setup with production values:
- Project: `fe-prod-467423`
- Image: `us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app:production-latest`
- Container name: `blender_app_prod`
- Production S3 buckets and environment variables

### Phase 4: Load Balancer & Routing Configuration

#### 4.1 Add Backend Service for Blender App
Update the load balancer configuration to include Blender app routing:

```terraform
# In load balancer configuration
backend_service "blender_api" {
  name        = "blender-api-backend"
  port_name   = "blender-port"
  protocol    = "HTTP"
  timeout_sec = 3600  # 1 hour for long-running Blender operations
  
  health_checks = [google_compute_health_check.blender_health.id]
  
  backend {
    group = google_compute_instance_group_manager.blender_instances.instance_group
  }
}
```

#### 4.2 URL Routing
Add path matcher for Blender API:
```terraform
path_matcher {
  name = "blender-api-matcher"
  default_service = blender_backend_service
  
  path_rule {
    paths = ["/api/v1/blender/*", "/api/v1/photo-realistic-view/*", 
             "/api/v1/product-2d-to-3d/*", "/api/v1/product-replacement/*",
             "/api/v1/usdz-to-glb/*"]
    service = blender_backend_service
  }
}
```

### Phase 5: Deployment Strategy

#### 5.1 Development Deployment Flow
```
1. Developer pushes to `develop` branch
2. GitHub Actions triggered
3. Build Docker image with BUILD_ENV=development
4. Push to: us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest
5. VM instances pull new image (via cron job or manual trigger)
6. Docker container restart with new image
7. Health check validates deployment
```

#### 5.2 Production Deployment Flow
```
1. Merge to `main` branch (via PR from develop)
2. GitHub Actions triggered
3. Build Docker image with BUILD_ENV=production
4. Push to: us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app:production-latest
5. Production VM instances pull new image
6. Blue-green or rolling deployment
7. Health check and monitoring
```

#### 5.3 Auto-Deployment on VM Instances
Create a systemd service or cron job on VMs:

**File**: `/etc/systemd/system/blender-app-updater.service`
```bash
#!/bin/bash
# Script to pull latest image and restart container

IMAGE="us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest"
CONTAINER_NAME="blender_app_dev"

# Authenticate to GCP Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Pull latest image
docker pull $IMAGE

# Stop and remove old container
docker stop $CONTAINER_NAME || true
docker rm $CONTAINER_NAME || true

# Start new container
docker run -d \
  --name $CONTAINER_NAME \
  -p 8000:8000 \
  --env-file /etc/blender-app/.env \
  -v /var/log/blender-app:/app/logs \
  -v /var/blender-working:/app/working_data \
  $IMAGE
```

### Phase 6: Monitoring & Logging

#### 6.1 Health Check Endpoint
Already exists: `/health` at port 8000

#### 6.2 Logging Strategy
- **Application Logs**: `/var/log/blender-app/` on VM
- **Container Logs**: Docker logs
- **GCP Cloud Logging**: Forward logs using Fluentd/Cloud Logging agent

#### 6.3 Monitoring Metrics
- Container health status
- API response times
- Blender processing duration
- S3/SQS integration status
- Memory and CPU usage

### Phase 7: Security Considerations

#### 7.1 Secrets Management
- **AWS Credentials**: Use GCP Workload Identity or Secret Manager
- **Environment Variables**: Store in Terraform variables or GCP Secret Manager
- **Service Account Keys**: Rotate regularly, minimal permissions

#### 7.2 Network Security
- **Firewall Rules**: Only allow necessary ports (8000 for Blender API)
- **VPC Configuration**: Use shared VPC for internal communication
- **HTTPS**: Terminate SSL at load balancer

#### 7.3 Container Security
- Use minimal base image (python:3.10-slim)
- Regular security updates
- No hardcoded credentials
- Run as non-root user

## Implementation Checklist

### Prerequisites
- [ ] Verify GCP projects exist (fe-dev-467323, fe-prod-467423)
- [ ] Verify Artifact Registry repositories exist
- [ ] Create/verify GCP service accounts for CI/CD
- [ ] Generate and store service account keys in GitHub Secrets

### Development Environment
- [ ] Create `.github/workflows/ci.yml`
- [ ] Create `ci/Dockerfile`
- [ ] Update `nest-infra/opentofu/gcp/departments/frontend/development/fe-dev/main.tf`
- [ ] Update `nest-infra/opentofu/gcp/departments/frontend/development/fe-dev/variables.tf`
- [ ] Apply Terraform changes
- [ ] Test GitHub Actions workflow on develop branch
- [ ] Verify container deployment on dev VM
- [ ] Test health endpoint and API functionality

### Production Environment
- [ ] Update `nest-infra/opentofu/gcp/departments/frontend/production/fe-prod/main.tf`
- [ ] Update production variables
- [ ] Apply Terraform changes for production
- [ ] Test deployment pipeline on main branch
- [ ] Configure production monitoring and alerts
- [ ] Document rollback procedures

### Load Balancer & Routing
- [ ] Add backend service for Blender app
- [ ] Configure health checks
- [ ] Add URL path routing rules
- [ ] Test external access through load balancer

### Post-Deployment
- [ ] Set up log forwarding to Cloud Logging
- [ ] Configure monitoring dashboards
- [ ] Create runbook for common operations
- [ ] Schedule regular image updates
- [ ] Plan for zero-downtime deployments

## Key Differences from Next.js Apps

| Aspect | Next.js Apps | Blender App |
|--------|-------------|-------------|
| **Runtime** | Node.js 20 | Python 3.10 |
| **Process Manager** | PM2 | Uvicorn (or add Supervisor) |
| **Port** | 3000 | 8000 |
| **Build Time** | pnpm build | pip install (no build step) |
| **Workers** | PM2 cluster | Uvicorn workers (4) |
| **Memory** | ~512MB-1GB | ~4GB (Blender intensive) |
| **Timeout** | Standard | Extended (3600s for Blender) |

## Resource Requirements

### Development
- **CPU**: 2 cores
- **Memory**: 4GB
- **Storage**: 20GB
- **Network**: Standard

### Production
- **CPU**: 4 cores
- **Memory**: 8GB
- **Storage**: 50GB (for Blender files)
- **Network**: High bandwidth for S3 transfers

## Rollback Strategy

1. **Quick Rollback**: Revert to previous image tag in Terraform
2. **Image Tagging**: Use git commit SHA for traceability
3. **Health Checks**: Automatic rollback on failed health checks
4. **Backup**: Keep last 3 working images in Artifact Registry

## Cost Estimation

### GCP Costs (Per Environment)
- **Artifact Registry**: $0.10/GB storage
- **VM Instance**: ~$50-150/month (depends on size)
- **Load Balancer**: ~$18/month base + traffic
- **Data Transfer**: Variable based on usage

### GitHub Actions
- Free for public repos
- Private repos: 2000 minutes/month free

## Next Steps

1. **Review this plan** with infrastructure team
2. **Create GitHub repository secrets** for GCP service accounts
3. **Start with development environment** implementation
4. **Test thoroughly** before production deployment
5. **Document operational procedures** for the team
6. **Set up monitoring and alerting** from day one

## Questions to Resolve

1. Should Blender be installed in the container or use API/Cloud service?
2. What's the expected traffic/load for the Blender API?
3. Do we need auto-scaling for this service?
4. Should we use Cloud Run instead of VMs for better scaling?
5. What's the retention policy for Blender-generated files?
6. Do we need a separate database for this service?

## Alternative: Cloud Run Deployment

If VMs are not required, consider Cloud Run for:
- Auto-scaling
- Pay-per-use pricing
- Simplified deployment
- Better integration with GCP services

This would follow the pattern in `nest-infra/opentofu/gcp/departments/ai-ml/` instead.

---

**Created**: February 8, 2026  
**Status**: Planning Phase  
**Owner**: Infrastructure Team  
**Priority**: Medium
