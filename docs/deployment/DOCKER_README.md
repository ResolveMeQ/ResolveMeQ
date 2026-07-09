# 🐳 ResolveMeQ Docker Deployment

Complete Docker-based deployment solution for ResolveMeQ platform with GitHub Actions CI/CD.

## 🏗️ Quick Start

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/your-org/resolvemeq.git
cd resolvemeq

# 2. Create environment file
cp .env.example .env
# Edit .env with your settings

# 3. Start services
docker compose up -d

# 4. Run migrations
docker compose exec web python manage.py migrate

# 5. Create superuser
docker compose exec web python manage.py createsuperuser

# Access at http://localhost:8000
```

### Production Deployment to VPS

```bash
# 1. Prepare VPS (one-time)
ssh root@your-vps
bash <(curl -s https://raw.githubusercontent.com/your-org/resolvemeq/main/scripts/vps-setup.sh)

# 2. Configure GitHub Secrets (one-time)
# Go to Settings → Secrets and add:
#   - VPS_SSH_PRIVATE_KEY
#   - DB_PASSWORD
#   - REDIS_PASSWORD
#   - SECRET_KEY
#   - SENTRY_DSN
#   - etc.

# 3. Deploy via GitHub Actions
# Go to Actions → Deploy to VPS → Run workflow
# Fill in:
#   - Image Tag: latest
#   - VPS Host: your-vps-ip
#   - SSH User: root
#   - Deployment Path: /opt/resolvemeq
```

## 📁 File Structure

```
resolvemeq/
├── Dockerfile.web                 # Django web application
├── Dockerfile                     # Celery worker
├── docker-compose.yml             # Local development
├── docker-compose.production.yml  # Production deployment
├── nginx.conf                     # Nginx configuration
├── .env.production.example        # Production env template
├── .github/workflows/
│   ├── build-and-push.yml        # Build & push to GHCR
│   └── deploy-to-vps.yml         # Deploy to VPS
├── scripts/
│   ├── vps-setup.sh              # VPS preparation script
│   └── test-docker-setup.sh      # Local testing script
└── resolvemeq-agent/
    ├── Dockerfile                 # FastAPI agent
    └── .github/workflows/
        └── build-and-push.yml     # Build & push agent
```

## 🚀 Deployment Workflows

### Automatic Build on Push

Every push to `main` triggers:
1. ✅ Build Docker images  
2. ✅ Run tests 
3. ✅ Push to GitHub Container Registry
4. ✅ Tag with commit SHA and `latest`

### Manual Deployment

**Deploy to VPS** workflow (manual trigger):
1. ✅ Copy docker-compose.yml to VPS
2. ✅ Create/update .env from GitHub Secrets
3. ✅ Pull images from GHCR
4. ✅ Run database migrations
5. ✅ Collect static files
6. ✅ Start all services
7. ✅ Health checks

## 🔧 Configuration

### Required GitHub Secrets

| Secret | Description | Example |
|--------|-------------|---------|
| `VPS_SSH_PRIVATE_KEY` | SSH private key for VPS | `-----BEGIN OPENSSH...` |
| `DB_NAME` | Database name | `resolvemeq_prod` |
| `DB_USER` | Database user | `resolvemeq_user` |
| `DB_PASSWORD` | Database password | `strong_password_123` |
| `REDIS_PASSWORD` | Redis password | `redis_secure_pass` |
| `SECRET_KEY` | Django secret key | `50+ random characters` |
| `ALLOWED_HOSTS` | Allowed hostnames | `domain.com,www.domain.com` |
| `SENTRY_DSN` | Sentry monitoring | `https://...@sentry.io/...` |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_TAG` | `latest` | Docker image tag for web/celery |
| `AGENT_IMAGE_TAG` | `latest` | Docker image tag for agent |
| `DEBUG` | `False` | Django debug mode |
| `ENVIRONMENT` | `production` | Deployment environment |

## 🐳 Docker Services

### Web (Django)
- **Image**: `ghcr.io/your-org/resolvemeq-web`
- **Port**: 8000
- **Health**: `/api/tickets/analytics/`

### Agent (FastAPI)
- **Image**: `ghcr.io/your-org/resolvemeq-agent`
- **Port**: 8000 (internal)
- **Health**: `/docs`

### Celery Worker
- **Image**: `ghcr.io/your-org/resolvemeq-celery`
- **Command**: `celery -A resolvemeq worker`

### PostgreSQL
- **Image**: `postgres:15-alpine`
- **Port**: 5432 (internal)
- **Volume**: `postgres_data`

### Redis
- **Image**: `redis:7-alpine`
- **Port**: 6379 (internal)
- **Volume**: `redis_data`

### Nginx
- **Image**: `nginx:alpine`
- **Ports**: 80, 443
- **Config**: `nginx.conf`

## 📊 Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f web
docker compose logs -f agent

# Last 100 lines
docker compose logs --tail=100 web
```

### Service Status

```bash
docker compose ps
```

### Health Checks

```bash
# Django
curl http://localhost:8000/api/tickets/analytics/

# Agent
curl http://localhost:8001/docs

# Database
docker compose exec db pg_isready
```

## 🔄 Updates & Maintenance

### Update to New Version

```bash
# Via GitHub Actions
# Go to Actions → Deploy to VPS → Run workflow
# Change Image Tag to new version

# Or manually on VPS
cd /opt/resolvemeq
docker compose pull
docker compose up -d
```

### Database Backup

```bash
# Backup
docker compose exec db pg_dump -U user dbname > backup.sql

# Restore
docker compose exec -T db psql -U user dbname < backup.sql
```

### Scale Services

```bash
# Scale Celery workers
docker compose up -d --scale celery_worker=3
```

## 🛠️ Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs service_name

# Restart
docker compose restart service_name

# Full restart
docker compose down && docker compose up -d
```

### Database Connection Issues

```bash
# Check database
docker compose exec db pg_isready

# Check connection
docker compose exec web python manage.py dbshell
```

### Clear Everything

```bash
# Stop and remove containers
docker compose down

# Remove volumes (⚠️  deletes data!)
docker compose down -v

# Remove images
docker compose down --rmi all
```

## 🔒 Security

- ✅ Non-root user in containers
- ✅ Environment variables for secrets
- ✅ Health checks configured
- ✅ Firewall rules (UFW)
- ✅ HTTPS with Nginx (configure SSL)
- ✅ Sentry monitoring
- ✅ Rate limiting in Nginx

## 📚 Documentation

- [Complete Deployment Guide](docs/DOCKER_DEPLOYMENT_GUIDE.md)
- [Platform Assessment](docs/trust/PLATFORM_ASSESSMENT.md)
- [Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)
- [Test Report](docs/TEST_REPORT.md)

## 🆘 Support

1. Check logs: `docker compose logs`
2. Review [Troubleshooting Guide](docs/DOCKER_DEPLOYMENT_GUIDE.md#troubleshooting)
3. Check Sentry for errors
4. Open GitHub issue

---

**Last Updated**: February 27, 2026  
**Version**: 1.0.0
