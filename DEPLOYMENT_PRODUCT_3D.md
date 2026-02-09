# Blender API Deployment to product-3d-dev-379843

## Overview

This deployment creates a **new `blender2` instance** in the existing `product-3d-dev-379843` project alongside the manually-created `blender1` instance. The setup uses:

- **Project**: `product-3d-dev-379843` (backend department)
- **Shared VPC**: `default-shared-vpc` (project: `shared-vpc-4466`)
- **Subnet**: `backend-dev-us-east4` (10.3.1.0/24)
- **Location**: `us-east4-a`
- **Machine**: `n1-standard-8` (8 vCPUs, 30 GB RAM)
- **GPU**: 1x NVIDIA T4
- **Managed by**: Terraform (blender1 remains manually managed)

## Architecture

```
Shared VPC (shared-vpc-4466)
└── backend-dev-us-east4 subnet (10.3.1.0/24)
    ├── blender1 (10.3.1.2) - Manual, DO NOT TOUCH
    └── blender2 (10.3.1.X) - Terraform-managed, NEW
```

## 🚀 Deployment Steps

### Step 1: Create Service Account for CI/CD

Since this is a new project setup, create a service account for GitHub Actions:

```bash
# Set project
gcloud config set project product-3d-dev-379843

# Create service account
gcloud iam service-accounts create cicd-github-actions \
  --display-name="GitHub Actions CICD" \
  --description="Service account for GitHub Actions CI/CD" \
  --project=product-3d-dev-379843

# Grant necessary permissions
gcloud projects add-iam-policy-binding product-3d-dev-379843 \
  --member="serviceAccount:cicd-github-actions@product-3d-dev-379843.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding product-3d-dev-379843 \
  --member="serviceAccount:cicd-github-actions@product-3d-dev-379843.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Create key
gcloud iam service-accounts keys create product-3d-dev-cicd-key.json \
  --iam-account=cicd-github-actions@product-3d-dev-379843.iam.gserviceaccount.com \
  --project=product-3d-dev-379843
```

### Step 2: Add GitHub Secret

1. Go to: **https://github.com/Nestingale/combined_blender_app/settings/secrets/actions**
2. Create new secret:
   - **Name**: `GCP_SA_KEY_PRODUCT_3D_DEV`
   - **Value**: Entire JSON content from `product-3d-dev-cicd-key.json`

### Step 3: Deploy Infrastructure with Terraform

```bash
cd nest-infra/opentofu/gcp/departments/backend/development/product-3d-dev/

# Initialize Terraform
tofu init

# Review the plan
tofu plan

# Apply changes (creates blender2, Artifact Registry, service accounts)
tofu apply
```

**What This Creates**:
- ✅ Compute instance `blender2` with GPU
- ✅ Artifact Registry repository `blender-containers`
- ✅ Service account `product-3d-dev-svc@product-3d-dev-379843.iam.gserviceaccount.com`
- ✅ IAM permissions for shared VPC access
- ✅ Startup script with Docker, NVIDIA drivers, auto-update

**What This Does NOT Touch**:
- ❌ `blender1` instance (remains untouched)
- ❌ Any existing configurations

### Step 4: Trigger CI/CD Build

```bash
# In combined_blender_app repository
git add .
git commit -m "Update CI/CD to use product-3d-dev project"
git push origin develop
```

This will:
1. Build Docker image
2. Push to: `us-east4-docker.pkg.dev/product-3d-dev-379843/blender-containers/blender_app:development-latest`
3. Auto-deploy to `blender2` via startup script timer

## 📦 What Gets Deployed

### Compute Instance: blender2

| Attribute | Value |
|-----------|-------|
| **Name** | blender2 |
| **Project** | product-3d-dev-379843 |
| **Zone** | us-east4-a |
| **Machine Type** | n1-standard-8 (8 vCPUs, 30 GB RAM) |
| **GPU** | 1x NVIDIA Tesla T4 |
| **Boot Disk** | 100 GB, pd-balanced, Ubuntu 24.04 LTS |
| **Network** | default-shared-vpc (shared-vpc-4466) |
| **Subnet** | backend-dev-us-east4 (10.3.1.0/24) |
| **Internal IP** | Auto-assigned from subnet |
| **External IP** | None (internal only) |
| **Port** | 8000 (Blender API) |
| **Tags** | backend-dev, ssh-allowed, blender-api |

### Container Configuration

- **Image**: `us-east4-docker.pkg.dev/product-3d-dev-379843/blender-containers/blender_app:development-latest`
- **Name**: `blender_app_dev`
- **GPU Access**: `--gpus all` (NVIDIA Container Toolkit)
- **Port Mapping**: `8000:8000`
- **Volumes**:
  - `/var/log/blender-app:/app/logs`
  - `/var/blender-working:/app/working_data`
- **Restart Policy**: `unless-stopped`
- **Auto-Update**: Every 5 minutes via systemd timer

### Artifact Registry

- **Location**: `us-east4`
- **Repository**: `blender-containers`
- **Format**: Docker
- **URL**: `us-east4-docker.pkg.dev/product-3d-dev-379843/blender-containers`

## 🔍 Verification

### Check Instance Status

```bash
# List instances (should see both blender1 and blender2)
gcloud compute instances list --project=product-3d-dev-379843 --filter="zone:us-east4-a"

# Get blender2 details
gcloud compute instances describe blender2 \
  --project=product-3d-dev-379843 \
  --zone=us-east4-a

# Check blender2 internal IP
gcloud compute instances describe blender2 \
  --project=product-3d-dev-379843 \
  --zone=us-east4-a \
  --format="get(networkInterfaces[0].networkIP)"
```

### SSH into blender2

```bash
gcloud compute ssh blender2 \
  --project=product-3d-dev-379843 \
  --zone=us-east4-a
```

Once inside:
```bash
# Check Docker
docker ps

# Check GPU
nvidia-smi

# Check container logs
docker logs blender_app_dev

# Test API
curl http://localhost:8000/health

# Check auto-updater timer
sudo systemctl status blender-updater.timer
```

### Check Artifact Registry

```bash
# List images
gcloud artifacts docker images list \
  us-east4-docker.pkg.dev/product-3d-dev-379843/blender-containers \
  --project=product-3d-dev-379843

# Get image details
gcloud artifacts docker images describe \
  us-east4-docker.pkg.dev/product-3d-dev-379843/blender-containers/blender_app:development-latest \
  --project=product-3d-dev-379843
```

## 🔧 Manual Operations

### Update Container Manually

If you need to manually update the container on blender2:

```bash
# SSH into instance
gcloud compute ssh blender2 --project=product-3d-dev-379843 --zone=us-east4-a

# Run update script
sudo /usr/local/bin/update-blender-container.sh
```

### Restart Container

```bash
docker restart blender_app_dev
```

### View Logs

```bash
# Container logs
docker logs -f blender_app_dev

# Application logs
tail -f /var/log/blender-app/*.log
```

### Stop Auto-Updater

```bash
sudo systemctl stop blender-updater.timer
sudo systemctl disable blender-updater.timer
```

## 🔐 Security & IAM

### Service Accounts

| Account | Purpose | Permissions |
|---------|---------|-------------|
| `cicd-github-actions@product-3d-dev-379843` | CI/CD deployments | Artifact Registry Writer, Storage Admin |
| `product-3d-dev-svc@product-3d-dev-379843` | Compute instance | Logging, Monitoring, Artifact Registry Reader, Network User (shared VPC) |

### Network Access

- **No external IP**: Access only via shared VPC internal network
- **Firewall**: Uses shared VPC firewall rules for `backend-dev` tag
- **SSH Access**: Via IAP or bastion host through shared VPC

## 🔄 CI/CD Pipeline

### Workflow Triggers

- **Branch**: `develop` → Development environment
- **Branch**: `main` → Production environment (if created)

### Build Process

```
Push to develop
    ↓
GitHub Actions triggered
    ↓
Build Docker image (ci/Dockerfile)
    ↓
Authenticate to GCP (product-3d-dev-379843)
    ↓
Push to us-east4-docker.pkg.dev/.../blender_app:development-latest
    ↓
blender2 auto-pulls new image (every 5 min)
    ↓
Container restart
    ↓
Health check
```

## 📊 Differences from Frontend Deployment

| Aspect | Frontend (fe-dev) | Backend (product-3d-dev) |
|--------|------------------|--------------------------|
| **Project** | fe-dev-467323 | product-3d-dev-379843 |
| **Department** | Frontend | Backend |
| **Subnet** | frontend-dev-us-central1 | backend-dev-us-east4 |
| **Region** | us-central1 | us-east4 |
| **Port** | 8000 | 8000 |
| **GPU** | None | 1x NVIDIA T4 |
| **Auto-Update** | Manual | Systemd timer (5 min) |
| **Management** | Multi-webapp module | Direct compute instance |

## 🛠️ Troubleshooting

### Build Fails in GitHub Actions

**Error**: `Failed to push to Artifact Registry`

**Solution**: Check secret `GCP_SA_KEY_PRODUCT_3D_DEV` is correctly set

### Instance Won't Start

**Error**: GPU quota exceeded

**Solution**: Request GPU quota increase in `product-3d-dev-379843`

```bash
gcloud compute project-info describe --project=product-3d-dev-379843
```

### Container Won't Pull Image

**Error**: `unauthorized: authentication required`

**Solution**: Ensure service account has Artifact Registry reader role

```bash
gcloud projects add-iam-policy-binding product-3d-dev-379843 \
  --member="serviceAccount:product-3d-dev-svc@product-3d-dev-379843.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
```

### GPU Not Available in Container

**Error**: `nvidia-smi` not found in container

**Solution**: Check NVIDIA Container Toolkit installation

```bash
# On instance
sudo systemctl status docker
sudo nvidia-container-cli info
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## 📝 Important Notes

1. **blender1 is UNTOUCHED**: Terraform only manages blender2
2. **Shared VPC**: Both instances use the same subnet (backend-dev-us-east4)
3. **Auto-updates**: blender2 checks for new images every 5 minutes
4. **GPU Support**: Requires NVIDIA drivers and Container Toolkit
5. **No External IP**: Access via internal network only

## 🎯 Next Steps

1. ✅ Test deployment with sample Blender operation
2. ✅ Configure load balancer for external access (if needed)
3. ✅ Set up monitoring and alerting
4. ✅ Plan production deployment strategy
5. ✅ Document migration path from blender1 → blender2

## 📞 Support

- **Terraform Issues**: Review Terraform state and plan
- **GPU Issues**: Check NVIDIA driver installation
- **Network Issues**: Verify shared VPC connectivity
- **CI/CD Issues**: Check GitHub Actions logs

---

**Created**: February 8, 2026  
**Project**: product-3d-dev-379843  
**Instance**: blender2  
**Status**: Ready for Deployment
