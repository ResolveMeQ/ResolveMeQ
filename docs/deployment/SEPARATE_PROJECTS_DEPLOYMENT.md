# 🎯 Separate Projects Deployment Guide

## Overview

ResolveMeQ consists of **TWO INDEPENDENT PROJECTS**:

1. **ResolveMeQ Backend** (Django) - Ticket management, knowledge base, APIs
2. **ResolveMeQ Agent** (FastAPI) - AI/ML autonomous agent for ticket resolution

Each project:
- ✅ Has its own repository
- ✅ Has its own Docker setup
- ✅ Has its own GitHub Actions workflows
- ✅ Can be deployed independently
- ✅ Communicates via HTTP APIs

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       VPS Server                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  Port 80/443                        │
│  │    Nginx     │───────────────────────────────────▶ Internet
│  │  (Reverse    │                                      │
│  │   Proxy)     │                                      │
│  └──────┬───────┘                                      │
│         │                                               │
│         ├─────────/api/────────▶ Django Backend        │
│         │                        (Port 8000)            │
│         │                        ┌─────────────┐        │
│         │                        │     Web     │        │
│         │                        ├─────────────┤        │
│         │                        │   Celery    │        │
│         │                        ├─────────────┤        │
│         │                        │ PostgreSQL  │        │
│         │                        ├─────────────┤        │
│         │                        │    Redis    │        │
│         │                        └─────────────┘        │
│         │                                               │
│         └─────────/agent/──────▶ AI Agent              │
│                                   (Port 8001)           │
│                                   ┌─────────────┐        │
│                                   │   FastAPI   │        │
│                                   │    Agent    │        │
│                                   └─────────────┘        │
│                                                         │
│  Docker Network: resolvemeq-shared (for communication)  │
└─────────────────────────────────────────────────────────┘
```

---

## Repository Structure

### Option A: Separate GitHub Repositories (Recommended)

```
GitHub
├── your-org/resolvemeq              # Django Backend
│   ├── Dockerfile.web
│   ├── docker-compose.yml           # Django only
│   ├── docker-compose.production.yml
│   └── .github/workflows/
│       ├── build-and-push.yml
│       └── deploy-to-vps.yml
│
└── your-org/resolvemeq-agent        # FastAPI Agent
    ├── Dockerfile
    ├── docker-compose.yml           # Agent only
    ├── docker-compose.production.yml
    └── .github/workflows/
        ├── build-and-push.yml
        └── deploy-to-vps.yml
```

### Option B: Monorepo (Current Structure)

```
resolvemeq/
├── ResolveMeQ/                      # Django Backend
│   ├── Dockerfile.web
│   ├── docker-compose.yml           # Django only
│   ├── docker-compose.production.yml
│   ├── docker-compose.local-fullstack.yml  # Optional: run both together
│   └── resolvemeq-agent/            # Git submodule or separate
│       ├── Dockerfile
│       ├── docker-compose.yml       # Agent only
│       └── docker-compose.production.yml
```

---

## Deployment Strategy

### 🎯 Three Components to Deploy

1. **Django Backend** → `/opt/resolvemeq`
2. **AI Agent** → `/opt/resolvemeq-agent`
3. **Infrastructure (Nginx)** → `/opt/resolvemeq-infrastructure`

---

## Step 1: Setup VPS (One-time)

### A. Prepare VPS

```bash
# SSH into VPS
ssh root@your-vps-ip

# Run VPS setup script (from Django repo)
curl -fsSL https://raw.githubusercontent.com/your-org/resolvemeq/main/scripts/vps-setup.sh | bash

# This installs:
# - Docker & Docker Compose
# - Configures firewall (UFW)
# - Creates deployment directories
# - Generates SSH keys
```

### B. Create Shared Docker Network

```bash
# This network allows Django ↔ Agent communication
docker network create resolvemeq-shared
```

### C. Add GitHub Secrets

#### For Django Repository

Settings → Secrets → Actions → New repository secret

| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `VPS_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | From VPS setup script |
| `DB_NAME` | `resolvemeq_prod` | PostgreSQL database name |
| `DB_USER` | `resolvemeq_user` | PostgreSQL username |
| `DB_PASSWORD` | `strong_password_123` | PostgreSQL password |
| `REDIS_PASSWORD` | `redis_secret_456` | Redis password |
| `SECRET_KEY` | `django-insecure-xyz...` | Django secret key (50+ chars) |
| `ALLOWED_HOSTS` | `api.domain.com,www.domain.com` | Allowed hosts |
| `AI_AGENT_URL` | `http://resolvemeq-agent-prod:8000` | Agent URL (Docker network) |
| `SENTRY_DSN` | `https://...@sentry.io/123` | Sentry monitoring URL |

#### For Agent Repository

| Secret Name | Example Value | Description |
|-------------|---------------|-------------|
| `VPS_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Same as Django |
| `DJANGO_KB_URL` | `http://resolvemeq-web-1:8000` | Django API URL (Docker network) |
| `AGENT_SENTRY_DSN` | `https://...@sentry.io/456` | Optional: Agent error tracking |

---

## Step 2: Deploy Django Backend

### A. Via GitHub Actions (Recommended)

1. Go to: **GitHub → resolvemeq repo → Actions → "Deploy Django Backend to VPS"**
2. Click **"Run workflow"**
3. Fill in:
   - Image tag: `latest` (or specific version)
   - VPS host: `123.45.67.89`
   - SSH user: `root`
   - Deployment path: `/opt/resolvemeq`
4. Click **"Run workflow"**

### B. Manual Deployment

```bash
# On your local machine
cd ResolveMeQ
git push origin main  # Triggers build

# SSH to VPS
ssh root@your-vps-ip
cd /opt/resolvemeq

# Create .env file
cat > .env << EOF
DB_NAME=resolvemeq_prod
DB_USER=resolvemeq_user
DB_PASSWORD=your_db_password
REDIS_PASSWORD=your_redis_password
SECRET_KEY=your_secret_key
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
AI_AGENT_URL=http://resolvemeq-agent-prod:8000
SENTRY_DSN=your_sentry_dsn
ENVIRONMENT=production
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
WEB_PORT=8000
EOF

# Login to GHCR
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u your-username --password-stdin

# Pull and start
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d

# Run migrations
docker compose -f docker-compose.production.yml exec web python manage.py migrate
docker compose -f docker-compose.production.yml exec web python manage.py collectstatic --noinput
```

---

## Step 3: Deploy AI Agent

### A. Via GitHub Actions (Recommended)

1. Go to: **GitHub → resolvemeq-agent repo → Actions → "Deploy Agent to VPS"**
2. Click **"Run workflow"**
3. Fill in:
   - Image tag: `latest`
   - VPS host: `123.45.67.89`
   - SSH user: `root`
   - Deployment path: `/opt/resolvemeq-agent`
4. Click **"Run workflow"**

### B. Manual Deployment

```bash
# SSH to VPS
ssh root@your-vps-ip
cd /opt/resolvemeq-agent

# Create .env file
cat > .env << EOF
DJANGO_KB_URL=http://resolvemeq-web-1:8000
PORT=8000
AGENT_PORT=8001
LOG_LEVEL=info
ENVIRONMENT=production
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
EOF

# Login to GHCR
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u your-username --password-stdin

# Pull and start
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
```

---

## Step 4: Deploy Infrastructure (Nginx)

### Using the Setup Script

```bash
# SSH to VPS
ssh root@your-vps-ip

# Run infrastructure setup
bash /opt/resolvemeq/scripts/setup-infrastructure.sh your-domain.com
```

This script:
1. Creates `/opt/resolvemeq-infrastructure` directory
2. Generates Nginx configuration with your domain
3. Obtains SSL certificate from Let's Encrypt
4. Starts Nginx and Certbot containers

### Manual Infrastructure Setup

```bash
# Create directory
mkdir -p /opt/resolvemeq-infrastructure
cd /opt/resolvemeq-infrastructure

# Copy infrastructure files
scp your-local-path/nginx.conf root@your-vps:/opt/resolvemeq-infrastructure/
scp your-local-path/docker-compose.infrastructure.yml root@your-vps:/opt/resolvemeq-infrastructure/docker-compose.yml

# Start infrastructure
docker compose up -d
```

---

## Communication Between Projects

### Docker Network Communication

Both projects join the `resolvemeq-shared` network:

```yaml
# Django: docker-compose.production.yml
networks:
  resolvemeq-backend:
    driver: bridge
  resolvemeq-shared:
    external: true  # Shared network

# Agent: docker-compose.production.yml
networks:
  resolvemeq-shared:
    external: true  # Same shared network
```

### Service Names

- Django web service: `resolvemeq-web-1` (auto-generated by compose)
- Agent service: `resolvemeq-agent-prod` (from container_name)

### Environment Variables

**Django** needs to know where Agent is:
```bash
AI_AGENT_URL=http://resolvemeq-agent-prod:8000
```

**Agent** needs to know where Django is:
```bash
DJANGO_KB_URL=http://resolvemeq-web-1:8000
```

---

## Local Development

### Option 1: Run Each Project Separately

**Terminal 1 - Django:**
```bash
cd ResolveMeQ
docker compose up -d
# Services: PostgreSQL, Redis, Django, Celery
# Access: http://localhost:8000
```

**Terminal 2 - Agent:**
```bash
cd resolvemeq-agent
# Update .env: DJANGO_KB_URL=http://host.docker.internal:8000
docker compose up -d
# Services: Agent only
# Access: http://localhost:8001
```

### Option 2: Run Full Stack Together

```bash
cd ResolveMeQ
docker compose -f docker-compose.local-fullstack.yml up -d
# Services: All of the above in one network
# Django: http://localhost:8000
# Agent: http://localhost:8001
```

---

## Verification

### Check Deployment Status

```bash
# On VPS
ssh root@your-vps-ip

# Django services
cd /opt/resolvemeq
docker compose ps
docker compose logs -f web

# Agent service
cd /opt/resolvemeq-agent
docker compose ps
docker compose logs -f agent

# Infrastructure
cd /opt/resolvemeq-infrastructure
docker compose ps
docker compose logs -f nginx
```

### Test Endpoints

```bash
# Health check
curl https://your-domain.com/health

# Django API
curl https://your-domain.com/api/tickets/analytics/

# Agent API
curl https://your-domain.com/agent/docs

# Admin panel
https://your-domain.com/admin/
```

---

## Deployment Workflow Comparison

### Before (Coupled)

```mermaid
graph LR
    A[Push to main] --> B[Build Django + Agent together]
    B --> C[Deploy both or nothing]
```

❌ Can't deploy Django without Agent  
❌ Can't deploy Agent without Django  
❌ One failure breaks everything

### After (Independent)

```mermaid
graph TD
    A1[Push Django repo] --> B1[Build Django images]
    B1 --> C1[Deploy Django independently]
    
    A2[Push Agent repo] --> B2[Build Agent image]
    B2 --> C2[Deploy Agent independently]
    
    C1 -.communicate via HTTP.-> C2
```

✅ Deploy Django without touching Agent  
✅ Deploy Agent without touching Django  
✅ Independent scaling and versioning  
✅ Isolated failures

---

## Troubleshooting

### Django can't reach Agent

```bash
# Check shared network
docker network inspect resolvemeq-shared

# Both services should be listed in "Containers"
# Verify AI_AGENT_URL in Django
docker compose -f docker-compose.production.yml exec web env | grep AI_AGENT_URL

# Test from Django container
docker compose exec web curl http://resolvemeq-agent-prod:8000/docs
```

### Agent can't reach Django

```bash
# Verify DJANGO_KB_URL in Agent
docker compose -f docker-compose.production.yml exec agent env | grep DJANGO_KB_URL

# Test from Agent container
docker compose exec agent curl http://resolvemeq-web-1:8000/api/tickets/analytics/
```

### Nginx can't route requests

```bash
# Check Nginx config
docker compose -f docker-compose.infrastructure.yml exec nginx nginx -t

# Check upstream connectivity
docker compose exec nginx ping resolvemeq-web-1
docker compose exec nginx ping resolvemeq-agent-prod

# View Nginx logs
docker compose logs -f nginx
```

---

## Migration from Old Setup

If you previously had both in one compose file:

1. **Backup data**
   ```bash
   docker compose exec db pg_dump -U user db > backup.sql
   ```

2. **Stop old services**
   ```bash
   docker compose down
   ```

3. **Deploy separately** following Steps 2 & 3 above

4. **Restore data** (if needed)
   ```bash
   docker compose -f docker-compose.production.yml exec -T db psql -U user db < backup.sql
   ```

---

## Summary

| Aspect | Django Backend | AI Agent | Infrastructure |
|--------|---------------|----------|----------------|
| **Repository** | `resolvemeq` | `resolvemeq-agent` | Shared config |
| **Deploy Path** | `/opt/resolvemeq` | `/opt/resolvemeq-agent` | `/opt/resolvemeq-infrastructure` |
| **Port** | 8000 | 8001 | 80, 443 |
| **Compose File** | `docker-compose.production.yml` | `docker-compose.production.yml` | `docker-compose.yml` |
| **Workflow** | `deploy-to-vps.yml` | `deploy-to-vps.yml` | Manual setup |
| **Dependencies** | PostgreSQL, Redis | None | Both services |
| **Scale** | Web, Celery worker, Beat | Single service | Nginx |

---

**Next Steps:**
1. Split agent into separate repo (if not done)
2. Test local development with separate setups
3. Deploy Django to VPS
4. Deploy Agent to VPS
5. Setup infrastructure (Nginx)
6. Configure DNS and SSL
7. Monitor both services independently
