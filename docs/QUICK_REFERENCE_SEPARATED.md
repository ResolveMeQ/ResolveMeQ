# 📋 Quick Reference: Separate Projects Setup

## TL;DR - What Changed?

**Before:** One docker-compose file with both Django + Agent  
**After:** Two independent projects, each with their own Docker setup

---

## File Structure

### ResolveMeQ Django Project
```
ResolveMeQ/
├── Dockerfile.web                        # Django production image
├── Dockerfile                            # Celery worker image
├── docker-compose.yml                    # Django ONLY (local dev)
├── docker-compose.production.yml         # Django ONLY (production)
├── docker-compose.local-fullstack.yml    # OPTIONAL: Both together (local)
├── docker-compose.infrastructure.yml     # OPTIONAL: Nginx orchestration
├── .env.example
├── .env.production.example
├── .github/workflows/
│   ├── build-and-push.yml               # Build Django images → GHCR
│   └── deploy-to-vps.yml                # Deploy Django ONLY
└── scripts/
    ├── vps-setup.sh
    ├── test-docker-setup.sh
    └── setup-infrastructure.sh           # Setup Nginx + SSL
```

### ResolveMeQ Agent Project
```
resolvemeq-agent/
├── Dockerfile                            # Agent image
├── docker-compose.yml                    # Agent ONLY (local dev)
├── docker-compose.production.yml         # Agent ONLY (production)
├── .env.example
├── .github/workflows/
│   ├── build-and-push.yml               # Build Agent image → GHCR
│   └── deploy-to-vps.yml                # Deploy Agent ONLY
```

---

## Environment Variables

### Django (.env)
```bash
# Database
DB_NAME=resolvemeq_prod
DB_USER=resolvemeq_user
DB_PASSWORD=strong_password_123

# Redis
REDIS_PASSWORD=redis_secret_456

# Django
SECRET_KEY=django-secret-key-50-chars
ALLOWED_HOSTS=api.domain.com,www.domain.com

# AI Agent Connection
AI_AGENT_URL=http://resolvemeq-agent-prod:8000  # Production (Docker network)
# AI_AGENT_URL=http://localhost:8001           # Local dev

# Monitoring
SENTRY_DSN=https://...@sentry.io/123

# GitHub
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
WEB_PORT=8000
```

### Agent (.env)
```bash
# Django Connection
DJANGO_KB_URL=http://resolvemeq-web-1:8000     # Production (Docker network)
# DJANGO_KB_URL=http://host.docker.internal:8000  # Local dev

# Agent Config
PORT=8000
AGENT_PORT=8001
LOG_LEVEL=info
ENVIRONMENT=production

# Monitoring (Optional)
SENTRY_DSN=https://...@sentry.io/456

# GitHub
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
```

---

## GitHub Secrets

### Django Repository Secrets

| Secret | Example | Required |
|--------|---------|----------|
| `VPS_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH...` | ✅ |
| `DB_NAME` | `resolvemeq_prod` | ✅ |
| `DB_USER` | `resolvemeq_user` | ✅ |
| `DB_PASSWORD` | `strong_password_123` | ✅ |
| `REDIS_PASSWORD` | `redis_secret_456` | ✅ |
| `SECRET_KEY` | `django-insecure-xyz...` | ✅ |
| `ALLOWED_HOSTS` | `api.domain.com,www.domain.com` | ✅ |
| `AI_AGENT_URL` | `http://resolvemeq-agent-prod:8000` | ✅ |
| `SENTRY_DSN` | `https://...@sentry.io/123` | ⚠️ Optional |

### Agent Repository Secrets

| Secret | Example | Required |
|--------|---------|----------|
| `VPS_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH...` | ✅ |
| `DJANGO_KB_URL` | `http://resolvemeq-web-1:8000` | ✅ |
| `AGENT_SENTRY_DSN` | `https://...@sentry.io/456` | ⚠️ Optional |

---

## Deployment Commands

### One-Time VPS Setup
```bash
# 1. Create shared network
docker network create resolvemeq-shared

# 2. Run setup script
bash /opt/resolvemeq/scripts/vps-setup.sh
```

### Deploy Django
```bash
# Via GitHub Actions
GitHub → resolvemeq repo → Actions → "Deploy Django Backend to VPS" → Run workflow

# Or manually
cd /opt/resolvemeq
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml exec web python manage.py migrate
docker compose -f docker-compose.production.yml exec web python manage.py collectstatic --noinput
```

### Deploy Agent
```bash
# Via GitHub Actions
GitHub → resolvemeq-agent repo → Actions → "Deploy Agent to VPS" → Run workflow

# Or manually
cd /opt/resolvemeq-agent
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
```

### Deploy Infrastructure (Nginx)
```bash
bash /opt/resolvemeq/scripts/setup-infrastructure.sh your-domain.com
```

---

## Local Development

### Run Django Only
```bash
cd ResolveMeQ
docker compose up -d
# Access: http://localhost:8000
```

### Run Agent Only
```bash
cd resolvemeq-agent
# Update .env: DJANGO_KB_URL=http://host.docker.internal:8000
docker compose up -d
# Access: http://localhost:8001
```

### Run Both Together (Optional)
```bash
cd ResolveMeQ
docker compose -f docker-compose.local-fullstack.yml up -d
# Django: http://localhost:8000
# Agent: http://localhost:8001
```

---

## Service Communication

### Production (Same VPS)
```
Django → Agent:     AI_AGENT_URL=http://resolvemeq-agent-prod:8000
Agent → Django:     DJANGO_KB_URL=http://resolvemeq-web-1:8000
Network:            resolvemeq-shared (Docker bridge)
```

### Local Development
```
Django → Agent:     AI_AGENT_URL=http://localhost:8001
                    OR AI_AGENT_URL=http://agent:8000 (if using fullstack compose)
Agent → Django:     DJANGO_KB_URL=http://host.docker.internal:8000
                    OR DJANGO_KB_URL=http://web:8000 (if using fullstack compose)
```

---

## Common Tasks

### Check Status
```bash
# Django
cd /opt/resolvemeq && docker compose ps

# Agent
cd /opt/resolvemeq-agent && docker compose ps

# Infrastructure
cd /opt/resolvemeq-infrastructure && docker compose ps
```

### View Logs
```bash
# Django
docker compose -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.production.yml logs -f celery_worker

# Agent
docker compose -f docker-compose.production.yml logs -f agent

# Nginx
docker compose logs -f nginx
```

### Update to New Version
```bash
# Django
cd /opt/resolvemeq
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml exec web python manage.py migrate

# Agent
cd /opt/resolvemeq-agent
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
```

### Restart Service
```bash
# Django web only
docker compose -f docker-compose.production.yml restart web

# Agent
docker compose -f docker-compose.production.yml restart agent

# Nginx
docker compose restart nginx
```

### Scale Services
```bash
# Scale Django workers
docker compose -f docker-compose.production.yml up -d --scale celery_worker=3

# Note: Agent doesn't need scaling (stateless FastAPI)
```

---

## Testing

### Test Connectivity
```bash
# From Django to Agent
docker compose exec web curl http://resolvemeq-agent-prod:8000/docs

# From Agent to Django
docker compose exec agent curl http://resolvemeq-web-1:8000/api/tickets/analytics/

# From Internet (via Nginx)
curl https://your-domain.com/health
curl https://your-domain.com/api/tickets/analytics/
curl https://your-domain.com/agent/docs
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Django can't reach Agent | Check `AI_AGENT_URL` env var, verify agent is on `resolvemeq-shared` network |
| Agent can't reach Django | Check `DJANGO_KB_URL` env var, verify Django is on `resolvemeq-shared` network |
| Nginx 502 Bad Gateway | Check upstream services are running, verify service names in nginx.conf |
| SSL certificate error | Re-run `setup-infrastructure.sh`, check certbot logs |
| Database migration fails | Check DB credentials in .env, verify PostgreSQL is healthy |
| Static files 404 | Run `collectstatic`, check static volume mount in nginx |

---

## Key Differences from Previous Setup

| Aspect | Before (Coupled) | After (Independent) |
|--------|------------------|---------------------|
| **Compose Files** | One file, all services | Separate files per project |
| **Agent Service** | In Django compose | Own compose file |
| **Network** | `resolvemeq-network` | `resolvemeq-shared` (external) |
| **Deployments** | Must deploy together | Deploy independently |
| **Repositories** | Can be same repo | Can be separate repos |
| **GitHub Actions** | One workflow | Separate workflows |
| **Scaling** | All or nothing | Per service |
| **Failures** | One fails, all down | Isolated failures |

---

## Documentation

- **[SEPARATE_PROJECTS_DEPLOYMENT.md](SEPARATE_PROJECTS_DEPLOYMENT.md)** - Complete deployment guide
- **[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)** - Original Docker guide (now outdated)
- **[DOCKER_README.md](DOCKER_README.md)** - Docker quick reference (update needed)

---

## Next Steps

1. ✅ Projects are now independent
2. ⬜ Move agent to separate GitHub repository (optional)
3. ⬜ Update .env files with correct URLs
4. ⬜ Test local development
5. ⬜ Deploy Django to VPS
6. ⬜ Deploy Agent to VPS
7. ⬜ Setup infrastructure (Nginx + SSL)
8. ⬜ Configure monitoring
