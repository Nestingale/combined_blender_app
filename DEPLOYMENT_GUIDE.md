# Blender API CI/CD - Quick Deployment Guide

## 📋 What Was Implemented

✅ GitHub Actions workflow for automated builds  
✅ Production-ready Docker configuration  
✅ Terraform configurations for dev and prod environments  
✅ Environment-specific configurations  

## 🚀 Quick Start

### 1. Set Up GitHub Secrets

In your GitHub repository settings (`Settings` → `Secrets and variables` → `Actions`), add:

| Secret Name | Description | How to Get |
|------------|-------------|-----------|
| `GCP_SA_KEY_FRONTEND_DEV` | GCP Service Account JSON for dev | From GCP Console for `fe-dev-svc@fe-dev-467323.iam.gserviceaccount.com` |
| `GCP_SA_KEY_FRONTEND_PROD` | GCP Service Account JSON for prod | From GCP Console for `fe-prod-svc@fe-prod-467423.iam.gserviceaccount.com` |

**To create service account keys:**
```bash
# For development
gcloud iam service-accounts keys create dev-key.json \
  --iam-account=fe-dev-svc@fe-dev-467323.iam.gserviceaccount.com \
  --project=fe-dev-467323

# For production  
gcloud iam service-accounts keys create prod-key.json \
  --iam-account=fe-prod-svc@fe-prod-467423.iam.gserviceaccount.com \
  --project=fe-prod-467423
```

Copy the entire JSON content and paste into GitHub Secrets.

### 2. Deploy Infrastructure (Terraform)

#### Development Environment
```bash
cd nest-infra/opentofu/gcp/departments/frontend/development/fe-dev/

# Initialize Terraform
tofu init

# Review changes
tofu plan

# Apply changes
tofu apply
```

#### Production Environment
```bash
cd nest-infra/opentofu/gcp/departments/frontend/production/fe-prod/

# Initialize Terraform
tofu init

# Review changes
tofu plan

# Apply changes (use caution in production!)
tofu apply
```

### 3. Trigger First Deployment

#### Development Deployment
```bash
git checkout develop
git add .
git commit -m "Add Blender API CI/CD"
git push origin develop
```

This will:
- Trigger GitHub Actions workflow
- Build Docker image with `BUILD_ENV=development`
- Push to: `us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest`

#### Production Deployment
```bash
git checkout main
git merge develop
git push origin main
```

This will:
- Trigger GitHub Actions workflow  
- Build Docker image with `BUILD_ENV=production`
- Push to: `us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app:production-latest`

## 📦 What Gets Deployed

### Development Environment
- **Project**: `fe-dev-467323`
- **Container**: `blender_app_dev`
- **Port**: `8000:8000`
- **Resources**: 2 CPU, 4GB RAM
- **Image**: `us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest`
- **Health Check**: `http://VM_IP:8000/health`

### Production Environment
- **Project**: `fe-prod-467423`
- **Container**: `blender_app_prod`  
- **Port**: `8001:8000` (external:internal)
- **Resources**: 4 CPU, 8GB RAM
- **Image**: `us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app:production-latest`
- **Health Check**: `http://VM_IP:8001/health`

## 🔍 Monitoring Deployment

### Check GitHub Actions
1. Go to your repository on GitHub
2. Click `Actions` tab
3. Watch the workflow run in real-time

### Check Docker Image in Artifact Registry
```bash
# Development
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app \
  --project=fe-dev-467323

# Production
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app \
  --project=fe-prod-467423
```

### Check Container on VM

SSH into your VM instance and run:

```bash
# Check if container is running
docker ps | grep blender_app

# View container logs
docker logs blender_app_dev   # or blender_app_prod

# Check health endpoint
curl http://localhost:8000/health

# Restart container (if needed)
docker restart blender_app_dev
```

## 🔧 Manual Container Deployment on VM

If you need to manually pull and run the container:

### Development
```bash
# Authenticate to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Pull latest image
docker pull us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest

# Stop and remove old container
docker stop blender_app_dev || true
docker rm blender_app_dev || true

# Run new container
docker run -d \
  --name blender_app_dev \
  -p 8000:8000 \
  --restart unless-stopped \
  -e AWS_REGION=us-east-1 \
  -e S3_BUCKET_NAME=nestingale-dev-digital-assets \
  -e LOG_LEVEL=INFO \
  -v /var/log/blender-app:/app/logs \
  -v /var/blender-working:/app/working_data \
  us-central1-docker.pkg.dev/fe-dev-467323/frontend-containers/blender_app:development-latest
```

### Production
```bash
# Authenticate to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Pull latest image
docker pull us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app:production-latest

# Stop and remove old container
docker stop blender_app_prod || true
docker rm blender_app_prod || true

# Run new container
docker run -d \
  --name blender_app_prod \
  -p 8001:8000 \
  --restart unless-stopped \
  -e AWS_REGION=us-east-1 \
  -e S3_BUCKET_NAME=nestingale-prod-digital-assets \
  -e LOG_LEVEL=INFO \
  -v /var/log/blender-app:/app/logs \
  -v /var/blender-working:/app/working_data \
  us-central1-docker.pkg.dev/fe-prod-467423/frontend-containers/blender_app:production-latest
```

## 📁 Files Created/Modified

### Combined Blender App Repository
```
combined_blender_app/
├── .github/
│   └── workflows/
│       └── ci.yml                           # NEW: GitHub Actions workflow
├── ci/
│   └── Dockerfile                            # NEW: Production Docker build
├── .dockerignore                             # MODIFIED: Optimized for CI
├── CICD_IMPLEMENTATION_PLAN.md              # NEW: Detailed plan
└── DEPLOYMENT_GUIDE.md                      # NEW: This file
```

### Nest-Infra Repository
```
nest-infra/opentofu/gcp/departments/frontend/
├── development/fe-dev/
│   ├── main.tf                              # MODIFIED: Added blender_app
│   └── variables.tf                         # MODIFIED: Added blender_app_env_vars
└── production/fe-prod/
    ├── main.tf                              # MODIFIED: Added blender_app
    └── variables.tf                         # MODIFIED: Added blender_app_env_vars
```

## 🔄 Workflow Diagram

```
Developer Push to develop/main
         ↓
GitHub Actions Triggered
         ↓
Build Docker Image (ci/Dockerfile)
         ↓
Authenticate to GCP
         ↓
Push to Artifact Registry
         ↓
[Manual or Automated Step]
VM pulls new image
         ↓
Container restart
         ↓
Health check validation
```

## 🛠️ Troubleshooting

### Build Fails in GitHub Actions
- **Check**: Secrets are correctly set (`GCP_SA_KEY_FRONTEND_DEV` or `GCP_SA_KEY_FRONTEND_PROD`)
- **Check**: Dockerfile syntax in `ci/Dockerfile`
- **Check**: All files referenced in Dockerfile exist

### Container Won't Start on VM
- **Check**: Docker logs: `docker logs blender_app_dev`
- **Check**: Port conflicts: `netstat -tulpn | grep 8000`
- **Check**: Environment variables are set correctly
- **Check**: Volumes exist: `ls -la /var/log/blender-app /var/blender-working`

### Health Check Fails
- **Check**: Container is running: `docker ps | grep blender`
- **Check**: Test endpoint: `curl http://localhost:8000/health`
- **Check**: Application logs for errors
- **Check**: Dependencies (Blender, Python packages) installed correctly

### Image Pull Fails
- **Check**: VM has correct IAM permissions
- **Check**: Artifact Registry authentication: `gcloud auth configure-docker us-central1-docker.pkg.dev`
- **Check**: Image exists in registry: `gcloud artifacts docker images list us-central1-docker.pkg.dev/.../blender_app`

## 🔐 Security Checklist

- [ ] Service account keys stored only in GitHub Secrets
- [ ] `.env` files not committed to repository
- [ ] Minimal IAM permissions for service accounts
- [ ] Container runs as non-root user (optional enhancement)
- [ ] Regular security updates scheduled
- [ ] Logs do not contain sensitive data

## 📊 Resource Costs Estimate

| Resource | Development | Production | Est. Monthly Cost |
|----------|------------|------------|-------------------|
| VM Instance | 2 CPU, 4GB | 4 CPU, 8GB | $80-$200 |
| Artifact Registry | Storage | Storage | $0.10/GB |
| Load Balancer | Shared | Shared | $18 base |
| Network Egress | Varies | Varies | $0.12/GB |

## 🎯 Next Steps

1. **Test the deployment pipeline** with a small change
2. **Set up monitoring** with Cloud Monitoring/Logging
3. **Configure load balancer** routing for external access
4. **Add auto-deployment** script on VMs (cron job or webhook)
5. **Set up alerts** for container failures
6. **Document API endpoints** for the team
7. **Plan rollback strategy** for production deployments

## 📞 Support

- Infrastructure Team: Review Terraform changes
- DevOps: Monitor CI/CD pipelines
- Application Team: Verify API functionality

---

**Last Updated**: February 8, 2026  
**Status**: Ready for Deployment  
**Version**: 1.0
