# Docker Deployment Guide

Complete guide for deploying ResolveMeQ and the AI Agent to VPS using Docker and GitHub Actions.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Local Development Setup](#local-development-setup)
4. [VPS Preparation](#vps-preparation)
5. [GitHub Configuration](#github-configuration)
6. [Deployment Process](#deployment-process)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

### Container Structure

```
┌─────────────────────────────────────────────────────────────┐
│                        VPS Server                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Nginx (Port 80/443)                 │   │
│  │           Reverse Proxy & Load Balancer              │   │
│  └────┬─────────────────────────┬─────────────────┬────┘   │
│       │                         │                 │         │
│  ┌────▼────────────┐  ┌────────▼──────────┐ ┌───▼─────┐   │
│  │  Django Web     │  │  AI Agent         │ │  Nginx  │   │
│  │  (Port 8000)    │  │  (Port 8000)      │ │ Static  │   │
│  └────┬────────────┘  └────────┬──────────┘ └─────────┘   │
│       │                         │                           │
│  ┌────▼─────────────────────────▼──────────────────────┐   │
│  │           Shared Docker Network                      │   │
│  │       (resolvemeq-network)                          │   │
│  └──┬────────────┬──────────────┬────────────────┬─────┘   │
│     │            │              │                │          │
│  ┌──▼──┐  ┌─────▼─────┐  ┌────▼─────┐   ┌─────▼──────┐   │
│  │Redis│  │PostgreSQL │  │  Celery  │   │Celery Beat │   │
│  └─────┘  └───────────┘  │  Worker  │   └────────────┘   │
│                           └──────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### Services

1. **Web** - Django application (gunicorn)
2. **Agent** - FastAPI ML service
3. **Celery Worker** - Background task processing
4. **Celery Beat** - Scheduled tasks
5. **PostgreSQL** - Database
6. **Redis** - Cache & message broker
7. **Nginx** - Reverse proxy

---

## 📦 Prerequisites

### On Your Local Machine

- Git
- Docker & Docker Compose
- GitHub account with repository access

### On VPS

- Ubuntu 20.04+ or Debian 11+
- Minimum 4GB RAM, 2 CPU cores
- 50GB storage
- Root or sudo access
- Public IP address or domain

---

## 🛠️ Local Development Setup

### 1. Clone Repositories

```bash
git clone https://github.com/your-org/resolvemeq.git
cd resolvemeq
```

### 2. Create Environment File

```bash
cp .env.example .env
# Edit .env with your local settings
```

### 3. Build and Run Locally

```bash
# Build images
docker compose build

# Start all services
docker compose up -d

# Check logs
docker compose logs -f

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser
```

### 4. Access Services

- Django: http://localhost:8000
- Agent API: http://localhost:8001
- Admin: http://localhost:8000/admin

---

## 🖥️ VPS Preparation

### 1. Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 2. Create Deployment Directory

```bash
sudo mkdir -p /opt/resolvemeq
sudo chown $USER:$USER /opt/resolvemeq
cd /opt/resolvemeq
```

### 3. Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 4. Create Environment File

```bash
cd /opt/resolvemeq
nano .env
```

Copy content from `.env.production.example` and fill in values:

```env
# Database
DB_NAME=resolvemeq_prod
DB_USER=resolvemeq_user
DB_PASSWORD=YOUR_STRONG_DB_PASSWORD

# Redis
REDIS_PASSWORD=YOUR_REDIS_PASSWORD

# Django
SECRET_KEY=YOUR_50_CHAR_SECRET_KEY
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,123.45.67.89

# Sentry
SENTRY_DSN=https://your-sentry-dsn@sentry.io/12345
ENVIRONMENT=production

# GitHub
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
AGENT_IMAGE_TAG=latest
```

---

## 🔐 GitHub Configuration

### 1. Repository Secrets

Go to **Settings → Secrets and variables → Actions** and add:

```
VPS_SSH_PRIVATE_KEY    # Your SSH private key for VPS access
DB_NAME                # Production database name
DB_USER                # Production database user
DB_PASSWORD            # Production database password
REDIS_PASSWORD         # Redis password
SECRET_KEY             # Django secret key
ALLOWED_HOSTS          # Comma-separated hostnames
SENTRY_DSN             # Sentry monitoring DSN
```

### 2. Generate SSH Key for VPS

```bash
# On your local machine
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy

# Copy private key content
cat ~/.ssh/github_deploy
# Add this to GitHub Secrets as VPS_SSH_PRIVATE_KEY

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-vps-ip
```

### 3. Enable GitHub Container Registry

The workflows are configured to push to GitHub Container Registry (ghcr.io). No additional setup needed - it uses the `GITHUB_TOKEN` automatically.

---

## 🚀 Deployment Process

### Automated Deployment via GitHub Actions

#### 1. Build and Push Images

Every push to `main` branch automatically:
1. Builds Docker images
2. Pushes to GitHub Container Registry
3. Tags with commit SHA and `latest`

```bash
# Push to main branch
git add .
git commit -m "Deploy: v1.0.0"
git push origin main
```

#### 2. Deploy to VPS

Go to **Actions → Deploy to VPS → Run workflow**

Fill in the form:
- **Image Tag**: `latest` or specific tag (e.g., `v1.0.0`, `main-abc123`)
- **Agent Image Tag**: `latest` or specific tag
- **VPS Host**: Your VPS IP or domain
- **SSH User**: `root` or your sudo user
- **Deployment Path**: `/opt/resolvemeq`

Click **Run workflow**.

#### 3. Monitor Deployment

Watch the workflow progress in GitHub Actions. It will:
1. ✅ Copy docker-compose.yml to VPS
2. ✅ Create/update .env file
3. ✅ Pull Docker images from GHCR
4. ✅ Run database migrations
5. ✅ Collect static files
6. ✅ Start all services
7. ✅ Run health checks

---

## 📊 Monitoring & Maintenance

### Check Service Status

```bash
ssh user@your-vps-ip
cd /opt/resolvemeq
docker compose ps
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f web
docker compose logs -f agent
docker compose logs -f celery_worker

# Last 100 lines
docker compose logs --tail=100 web
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart web
docker compose restart agent
```

### Update to New Version

**Option 1: Via GitHub Actions**
- Run "Deploy to VPS" workflow with new image tag

**Option 2: Manual Update**
```bash
cd /opt/resolvemeq

# Update image tags in .env
nano .env

# Pull new images
docker compose pull

# Restart services
docker compose up -d

# Check health
docker compose ps
```

### Database Backup

```bash
# Backup
docker compose exec db pg_dump -U resolvemeq_user resolvemeq_prod > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U resolvemeq_user resolvemeq_prod < backup_20260227.sql
```

### Scale Services

```bash
# Scale celery workers
docker compose up -d --scale celery_worker=3
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs service_name

# Check container status
docker compose ps

# Restart service
docker compose restart service_name
```

### Database Connection Issues

```bash
# Check database is running
docker compose ps db

# Check database logs
docker compose logs db

# Test connection
docker compose exec web python manage.py dbshell
```

### Image Pull Errors

```bash
# Re-login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull specific image
docker pull ghcr.io/your-org/resolvemeq-web:latest
```

### Port Already in Use

```bash
# Find process using port 80
sudo lsof -i :80

# Stop nginx if running
sudo systemctl stop nginx

# Or change ports in docker-compose.yml
```

### Out of Disk Space

```bash
# Clean up old images
docker image prune -a

# Clean up old volumes
docker volume prune

# Remove stopped containers
docker container prune
```

### Service Health Check Failing

```bash
# Check service logs
docker compose logs web

# Manual health check
curl http://localhost:8000/api/tickets/analytics/

# Restart with fresh state
docker compose down
docker compose up -d
```

---

## 🔒 Security Checklist

- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY (50+ characters)
- [ ] Enable firewall (ufw)
- [ ] Configure SSL/TLS certificates
- [ ] Set DEBUG=False in production
- [ ] Configure ALLOWED_HOSTS properly
- [ ] Use environment variables for secrets
- [ ] Enable Sentry monitoring
- [ ] Regular security updates
- [ ] Implement database backups
- [ ] Configure fail2ban for SSH protection

---

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)

---

## 🆘 Support

For issues or questions:
1. Check logs: `docker compose logs`
2. Review GitHub Actions workflow runs
3. Check Sentry for errors
4. Contact DevOps team

---

**Last Updated:** February 27, 2026  
**Version:** 1.0.0
