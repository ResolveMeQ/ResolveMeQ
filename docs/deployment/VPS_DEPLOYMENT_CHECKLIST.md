# ✅ VPS Deployment Checklist

Quick checklist for deploying ResolveMeQ to VPS. For detailed instructions, see [VPS_DEPLOYMENT_STEP_BY_STEP.md](VPS_DEPLOYMENT_STEP_BY_STEP.md).

---

## Pre-Deployment

- [ ] VPS provisioned (2GB+ RAM, 2+ CPU cores, Ubuntu 20.04/22.04)
- [ ] Domain DNS pointing to VPS IP address
- [ ] SSH access to VPS confirmed
- [ ] GitHub Personal Access Token created (`read:packages` scope)
- [ ] `.env` values prepared (SECRET_KEY, passwords, etc.)

---

## Initial VPS Setup

- [ ] SSH into VPS
- [ ] System updated: `sudo apt update && sudo apt upgrade -y`
- [ ] Essential tools installed: `sudo apt install -y curl git wget nano ufw`
- [ ] Non-root user created (optional): `sudo adduser deploy`
- [ ] Firewall configured:
  - [ ] `sudo ufw allow 22/tcp` (SSH)
  - [ ] `sudo ufw allow 80/tcp` (HTTP)
  - [ ] `sudo ufw allow 443/tcp` (HTTPS)
  - [ ] `sudo ufw enable`

---

## Docker Installation

- [ ] Docker installed: `curl -fsSL https://get.docker.com | sudo sh`
- [ ] User added to docker group: `sudo usermod -aG docker $USER`
- [ ] Docker Compose installed: `sudo apt install -y docker-compose-plugin`
- [ ] Docker verified: `docker --version && docker compose version`
- [ ] Docker enabled on boot: `sudo systemctl enable docker`

---

## Network Setup

- [ ] Shared network created: `docker network create resolvemeq-shared`
- [ ] Network verified: `docker network ls | grep resolvemeq-shared`

---

## GitHub Container Registry

- [ ] Logged in to GHCR: `echo TOKEN | docker login ghcr.io -u USERNAME --password-stdin`
- [ ] Login successful confirmed

---

## Django Backend Deployment

- [ ] Directory created: `sudo mkdir -p /opt/resolvemeq`
- [ ] Ownership set: `sudo chown -R $USER:$USER /opt/resolvemeq`
- [ ] `docker-compose.yml` created/copied
- [ ] `.env` file created with all variables:
  - [ ] `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - [ ] `REDIS_PASSWORD`
  - [ ] `SECRET_KEY` (generated)
  - [ ] `ALLOWED_HOSTS` (your domain)
  - [ ] `AI_AGENT_URL=http://resolvemeq-agent-prod:8000`
  - [ ] `GITHUB_REPOSITORY_OWNER`
- [ ] Images pulled: `docker compose pull`
- [ ] Services started: `docker compose up -d`
- [ ] Services healthy: `docker compose ps` (all showing "Up" and "healthy")
- [ ] Migrations run: `docker compose exec web python manage.py migrate`
- [ ] Static files collected: `docker compose exec web python manage.py collectstatic --noinput`
- [ ] Superuser created: `docker compose exec web python manage.py createsuperuser`
- [ ] Django verified: `curl http://localhost:8000/api/tickets/analytics/`

---

## AI Agent Deployment

- [ ] Directory created: `sudo mkdir -p /opt/resolvemeq-agent`
- [ ] Ownership set: `sudo chown -R $USER:$USER /opt/resolvemeq-agent`
- [ ] `docker-compose.yml` created
- [ ] `.env` file created:
  - [ ] `DJANGO_KB_URL=http://resolvemeq-web-1:8000`
  - [ ] `GITHUB_REPOSITORY_OWNER`
  - [ ] `AGENT_PORT=8001`
- [ ] Image pulled: `docker compose pull`
- [ ] Service started: `docker compose up -d`
- [ ] Service healthy: `docker compose ps`
- [ ] Agent verified: `curl http://localhost:8001/docs`
- [ ] Communication tested:
  - [ ] Django → Agent: `docker exec resolvemeq-web-1 curl http://resolvemeq-agent-prod:8000/docs`
  - [ ] Agent → Django: `docker exec resolvemeq-agent-prod curl http://resolvemeq-web-1:8000/api/tickets/analytics/`

---

## Nginx & SSL Setup

- [ ] Directory created: `sudo mkdir -p /opt/resolvemeq-infrastructure`
- [ ] Ownership set: `sudo chown -R $USER:$USER /opt/resolvemeq-infrastructure`
- [ ] `nginx.conf` created (with YOUR_DOMAIN replaced)
- [ ] `docker-compose.yml` created
- [ ] SSL certificate obtained:
  ```bash
  docker run --rm \
    -v $(pwd)/certbot_data:/etc/letsencrypt \
    -v $(pwd)/certbot_www:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@YOUR_DOMAIN \
    --agree-tos \
    -d YOUR_DOMAIN \
    -d www.YOUR_DOMAIN
  ```
- [ ] Certificate files exist: `ls certbot_data/live/YOUR_DOMAIN/`
- [ ] Nginx started: `docker compose up -d`
- [ ] Nginx healthy: `docker compose ps`

---

## Final Verification

- [ ] All containers running: `docker ps`
  - [ ] resolvemeq-db-1
  - [ ] resolvemeq-redis-1
  - [ ] resolvemeq-web-1
  - [ ] resolvemeq-celery_worker-1
  - [ ] resolvemeq-celery_beat-1
  - [ ] resolvemeq-agent-prod
  - [ ] resolvemeq-nginx
  - [ ] resolvemeq-certbot

- [ ] Public endpoints working:
  - [ ] `curl https://YOUR_DOMAIN/health` → "OK"
  - [ ] `curl https://YOUR_DOMAIN/api/tickets/analytics/` → JSON response
  - [ ] `curl https://YOUR_DOMAIN/agent/docs` → HTML response
  - [ ] Browser: `https://YOUR_DOMAIN/admin/` → Admin login page

- [ ] HTTPS working (no certificate warnings)
- [ ] Static files loading correctly
- [ ] Can login to admin panel

---

## Post-Deployment

- [ ] Backups configured
  - [ ] Backup script created: `/usr/local/bin/backup-resolvemeq.sh`
  - [ ] Cron job added: `0 2 * * * /usr/local/bin/backup-resolvemeq.sh`
  
- [ ] Monitoring setup
  - [ ] Sentry configured (optional)
  - [ ] Uptime monitoring (UptimeRobot, Pingdom, etc.)
  - [ ] Log rotation configured in `/etc/docker/daemon.json`
  
- [ ] Auto-updates configured (optional)
  - [ ] Watchtower installed for automatic updates
  
- [ ] Documentation
  - [ ] Environment variables documented
  - [ ] Custom configurations noted
  - [ ] Team trained on platform usage

---

## Testing Checklist

- [ ] Create test ticket via API
- [ ] Verify email notifications (if configured)
- [ ] Test ticket assignment
- [ ] Test AI agent analysis
- [ ] Test Slack integration (if configured)
- [ ] Test knowledge base search
- [ ] Verify Celery tasks running
- [ ] Check Celery beat scheduling
- [ ] Test file uploads (media files)
- [ ] Verify rate limiting working

---

## Quick Reference

### Directory Structure
```
/opt/
├── resolvemeq/               # Django Backend
│   ├── docker-compose.yml
│   └── .env
├── resolvemeq-agent/         # AI Agent
│   ├── docker-compose.yml
│   └── .env
└── resolvemeq-infrastructure/ # Nginx
    ├── docker-compose.yml
    ├── nginx.conf
    ├── certbot_data/
    └── certbot_www/
```

### Important Commands

**Check all services:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**View all logs:**
```bash
# Django
docker logs -f resolvemeq-web-1

# Agent
docker logs -f resolvemeq-agent-prod

# Nginx
docker logs -f resolvemeq-nginx
```

**Restart everything:**
```bash
cd /opt/resolvemeq && docker compose restart
cd /opt/resolvemeq-agent && docker compose restart
cd /opt/resolvemeq-infrastructure && docker compose restart
```

**Update to latest version:**
```bash
cd /opt/resolvemeq && docker compose pull && docker compose up -d
cd /opt/resolvemeq-agent && docker compose pull && docker compose up -d
docker exec resolvemeq-web-1 python manage.py migrate
docker exec resolvemeq-web-1 python manage.py collectstatic --noinput
```

---

## Troubleshooting Quick Fixes

**502 Bad Gateway:**
```bash
# Check backends are running
docker ps | grep resolvemeq
docker restart resolvemeq-web-1
docker restart resolvemeq-agent-prod
```

**Database connection issues:**
```bash
# Check database
docker logs resolvemeq-db-1
docker restart resolvemeq-db-1
```

**SSL certificate issues:**
```bash
# Renew certificate
cd /opt/resolvemeq-infrastructure
docker compose exec certbot certbot renew
docker restart resolvemeq-nginx
```

**Out of memory:**
```bash
# Check resources
docker stats
free -h
df -h

# Clean up
docker system prune -a
```

---

## GitHub Actions Setup

### Required Secrets (Settings → Secrets and variables → Actions)

**For Django Repository:**
- [ ] `VPS_HOST` - Your VPS IP address
- [ ] `VPS_SSH_KEY` - Private SSH key for VPS access
- [ ] `VPS_SSH_USER` - SSH username (e.g., `deploy` or `root`)
- [ ] `GHCR_TOKEN` - GitHub Personal Access Token
- [ ] `AI_AGENT_URL` - `http://resolvemeq-agent-prod:8000`
- [ ] All Django `.env` variables as secrets

**For Agent Repository:**
- [ ] `VPS_HOST` - Same as above
- [ ] `VPS_SSH_KEY` - Same as above
- [ ] `VPS_SSH_USER` - Same as above
- [ ] `GHCR_TOKEN` - Same as above
- [ ] `DJANGO_KB_URL` - `http://resolvemeq-web-1:8000`

### Manual Deployment Trigger

**Deploy Django:**
1. Go to: `https://github.com/YOUR_ORG/ResolveMeQ/actions/workflows/deploy-to-vps.yml`
2. Click "Run workflow"
3. Enter image tag (e.g., `latest` or `v1.0.0`)
4. Click "Run workflow"

**Deploy Agent:**
1. Go to: `https://github.com/YOUR_ORG/resolvemeq-agent/actions/workflows/deploy-to-vps.yml`
2. Click "Run workflow"
3. Enter image tag
4. Click "Run workflow"

---

**💡 Tip:** Print this checklist and check off items as you complete them!

**📚 For detailed explanations, see:** [VPS_DEPLOYMENT_STEP_BY_STEP.md](VPS_DEPLOYMENT_STEP_BY_STEP.md)
