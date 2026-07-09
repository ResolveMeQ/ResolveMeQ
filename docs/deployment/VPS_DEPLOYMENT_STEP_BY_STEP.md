# 🚀 VPS Deployment Guide - Step by Step

Complete guide to deploy ResolveMeQ Django Backend + AI Agent on a VPS.

---

## 📋 Prerequisites

### What You Need:
- ✅ VPS with Ubuntu 20.04+ or Debian 11+ (minimum 2GB RAM, 2 CPU cores)
- ✅ Root or sudo access to the VPS
- ✅ Domain name pointing to your VPS IP (e.g., `resolvemeq.com`)
- ✅ GitHub account with both repositories
- ✅ Basic SSH knowledge

### Required Accounts:
- GitHub account (for GHCR - GitHub Container Registry)
- Sentry account (optional, for error monitoring)
- Email service (optional, for notifications)

---

## 🎯 Overview

We'll deploy:
1. **Django Backend** → `/opt/resolvemeq` (Port 8000)
2. **AI Agent** → `/opt/resolvemeq-agent` (Port 8001)
3. **Nginx** → `/opt/resolvemeq-infrastructure` (Ports 80, 443)

```
Internet (Port 80/443)
    ↓
  Nginx
    ├─→ /api/ → Django Backend (8000)
    └─→ /agent/ → AI Agent (8001)
```

---

## Step 1: Initial VPS Setup

### 1.1 Connect to Your VPS

```bash
# From your local machine
ssh root@YOUR_VPS_IP

# If using a different user:
ssh username@YOUR_VPS_IP
```

### 1.2 Update System

```bash
# Update package lists
sudo apt update

# Upgrade installed packages
sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl git wget nano vim ufw
```

### 1.3 Create a Non-Root User (Optional but Recommended)

```bash
# Create user
sudo adduser deploy

# Add to sudo group
sudo usermod -aG sudo deploy

# Switch to new user
su - deploy
```

**From now on, you can use either root or the deploy user.**

---

## Step 2: Install Docker & Docker Compose

### 2.1 Install Docker

```bash
# Download Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh

# Run the script
sudo sh get-docker.sh

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Apply group changes (or logout and login again)
newgrp docker

# Verify Docker installation
docker --version
# Expected: Docker version 24.x.x or higher
```

### 2.2 Install Docker Compose

```bash
# Install Docker Compose plugin (recommended method)
sudo apt install -y docker-compose-plugin

# Verify installation
docker compose version
# Expected: Docker Compose version v2.x.x or higher
```

### 2.3 Enable Docker to Start on Boot

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

## Step 3: Configure Firewall

```bash
# Enable UFW
sudo ufw enable

# Allow SSH (IMPORTANT: Do this first!)
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Check firewall status
sudo ufw status

# Expected output:
# Status: active
# To                         Action      From
# --                         ------      ----
# 22/tcp                     ALLOW       Anywhere
# 80/tcp                     ALLOW       Anywhere
# 443/tcp                    ALLOW       Anywhere
```

---

## Step 4: Create Shared Docker Network

```bash
# Create the network that both projects will use
docker network create resolvemeq-shared

# Verify
docker network ls | grep resolvemeq-shared

# Expected: resolvemeq-shared listed
```

---

## Step 5: Setup GitHub Container Registry Access

### 5.1 Create GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Name it: `VPS Docker Pull Access`
4. Select scopes:
   - ✅ `read:packages` (Download packages)
   - ✅ `write:packages` (Optional, if you'll push from VPS)
5. Click **"Generate token"**
6. **Copy the token** (you won't see it again!)

### 5.2 Login to GHCR on VPS

```bash
# Login to GitHub Container Registry
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Expected: Login Succeeded
```

---

## Step 6: Deploy Django Backend

### 6.1 Create Django Deployment Directory

```bash
# Create directory
sudo mkdir -p /opt/resolvemeq
cd /opt/resolvemeq

# Set ownership
sudo chown -R $USER:$USER /opt/resolvemeq
```

### 6.2 Download Docker Compose File

**Option A: Clone the Repository**

```bash
# Clone Django repo
git clone https://github.com/YOUR_ORG/ResolveMeQ.git /tmp/resolvemeq-temp

# Copy only what we need
cp /tmp/resolvemeq-temp/docker-compose.production.yml /opt/resolvemeq/docker-compose.yml

# Cleanup
rm -rf /tmp/resolvemeq-temp
```

**Option B: Manual Creation**

```bash
nano /opt/resolvemeq/docker-compose.yml
```

Paste this content:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - resolvemeq-backend
      - resolvemeq-shared

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: [ "CMD", "redis-cli", "--pass", "${REDIS_PASSWORD}", "ping" ]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - resolvemeq-backend

  web:
    image: ghcr.io/${GITHUB_REPOSITORY_OWNER}/resolvemeq-web:${IMAGE_TAG:-latest}
    restart: unless-stopped
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media
    ports:
      - "${WEB_PORT:-8000}:8000"
    environment:
      - DEBUG=False
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - AI_AGENT_URL=${AI_AGENT_URL}
      - SECRET_KEY=${SECRET_KEY}
      - SENTRY_DSN=${SENTRY_DSN}
      - ENVIRONMENT=production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/tickets/analytics/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - resolvemeq-backend
      - resolvemeq-shared

  celery_worker:
    image: ghcr.io/${GITHUB_REPOSITORY_OWNER}/resolvemeq-celery:${IMAGE_TAG:-latest}
    restart: unless-stopped
    volumes:
      - media_files:/app/media
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - AI_AGENT_URL=${AI_AGENT_URL}
      - SECRET_KEY=${SECRET_KEY}
      - SENTRY_DSN=${SENTRY_DSN}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      web:
        condition: service_healthy
    networks:
      - resolvemeq-backend
      - resolvemeq-shared

  celery_beat:
    image: ghcr.io/${GITHUB_REPOSITORY_OWNER}/resolvemeq-celery:${IMAGE_TAG:-latest}
    restart: unless-stopped
    command: celery -A resolvemeq beat -l info
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - resolvemeq-backend

networks:
  resolvemeq-backend:
    driver: bridge
  resolvemeq-shared:
    external: true

volumes:
  postgres_data:
    name: resolvemeq_postgres_data
  redis_data:
    name: resolvemeq_redis_data
  static_files:
    name: resolvemeq_static_files
  media_files:
    name: resolvemeq_media_files
```

Save and exit (`Ctrl+X`, then `Y`, then `Enter`).

### 6.3 Create Environment File

```bash
nano /opt/resolvemeq/.env
```

Paste and **customize** these values:

```bash
# Database Configuration
DB_NAME=resolvemeq_prod
DB_USER=resolvemeq_user
DB_PASSWORD=CHANGE_ME_TO_STRONG_PASSWORD_123

# Redis Configuration
REDIS_PASSWORD=CHANGE_ME_TO_STRONG_REDIS_PASSWORD_456

# Django Configuration
SECRET_KEY=CHANGE_ME_TO_RANDOM_50_CHARS_django-insecure-xyz123abc456
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_VPS_IP

# AI Agent Connection (we'll set this up later)
AI_AGENT_URL=http://resolvemeq-agent-prod:8000

# Sentry Configuration (optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
ENVIRONMENT=production

# GitHub Configuration
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
WEB_PORT=8000
```

**Generate a strong SECRET_KEY:**

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and use it for `SECRET_KEY`.

Save and exit.

### 6.4 Pull Docker Images

```bash
cd /opt/resolvemeq

# Pull the images
docker compose pull

# Expected: Three images pulled
# - postgres:15-alpine
# - redis:7-alpine
# - ghcr.io/your-org/resolvemeq-web:latest
# - ghcr.io/your-org/resolvemeq-celery:latest
```

### 6.5 Start Django Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# Expected: All services showing "Up" and "healthy"
```

### 6.6 Run Database Migrations

```bash
# Run migrations
docker compose exec web python manage.py migrate

# Expected: Migrations applied successfully
```

### 6.7 Collect Static Files

```bash
# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Expected: Static files copied to /app/staticfiles
```

### 6.8 Create Superuser

```bash
# Create admin user
docker compose exec web python manage.py createsuperuser

# Follow prompts:
# Email: admin@your-domain.com
# Password: (choose strong password)
# Password (again): (repeat)
```

### 6.9 Verify Django is Running

```bash
# Check logs
docker compose logs -f web

# Test the API endpoint
curl http://localhost:8000/api/tickets/analytics/

# Expected: JSON response with analytics data
```

**✅ Django Backend is now running!**

---

## Step 7: Deploy AI Agent

### 7.1 Create Agent Deployment Directory

```bash
# Create directory
sudo mkdir -p /opt/resolvemeq-agent
cd /opt/resolvemeq-agent

# Set ownership
sudo chown -R $USER:$USER /opt/resolvemeq-agent
```

### 7.2 Create Docker Compose File

```bash
nano /opt/resolvemeq-agent/docker-compose.yml
```

Paste this content:

```yaml
version: '3.8'

services:
  agent:
    image: ghcr.io/${GITHUB_REPOSITORY_OWNER}/resolvemeq-agent:${IMAGE_TAG:-latest}
    container_name: resolvemeq-agent-prod
    restart: unless-stopped
    ports:
      - "${AGENT_PORT:-8001}:8000"
    environment:
      - DJANGO_KB_URL=${DJANGO_KB_URL}
      - PORT=8000
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - ENVIRONMENT=production
      - SENTRY_DSN=${SENTRY_DSN}
    volumes:
      - agent_data:/app/data
      - agent_cache:/app/.cache
      - agent_models:/app/models
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - resolvemeq-shared
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

networks:
  resolvemeq-shared:
    external: true

volumes:
  agent_data:
    name: resolvemeq_agent_data
  agent_cache:
    name: resolvemeq_agent_cache
  agent_models:
    name: resolvemeq_agent_models
```

Save and exit.

### 7.3 Create Environment File

```bash
nano /opt/resolvemeq-agent/.env
```

Paste this content:

```bash
# Django Backend URL (Docker network)
DJANGO_KB_URL=http://resolvemeq-web-1:8000

# Agent Configuration
PORT=8000
AGENT_PORT=8001
LOG_LEVEL=info
ENVIRONMENT=production

# Error Tracking (optional)
SENTRY_DSN=

# GitHub Configuration
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
```

Save and exit.

### 7.4 Pull and Start Agent

```bash
cd /opt/resolvemeq-agent

# Pull image
docker compose pull

# Start agent
docker compose up -d

# Check status
docker compose ps

# Expected: resolvemeq-agent-prod showing "Up" and "healthy"
```

### 7.5 Verify Agent is Running

```bash
# Check logs
docker compose logs -f agent

# Test agent endpoint
curl http://localhost:8001/docs

# Expected: HTML response with FastAPI docs
```

### 7.6 Test Communication Between Django and Agent

```bash
# From Django container, ping agent
docker exec resolvemeq-web-1 curl -s http://resolvemeq-agent-prod:8000/docs | head -n 5

# Expected: HTML response

# From Agent container, ping Django
docker exec resolvemeq-agent-prod curl -s http://resolvemeq-web-1:8000/api/tickets/analytics/

# Expected: JSON response
```

**✅ AI Agent is now running and communicating with Django!**

---

## Step 8: Setup Nginx Reverse Proxy

### 8.1 Create Infrastructure Directory

```bash
sudo mkdir -p /opt/resolvemeq-infrastructure
cd /opt/resolvemeq-infrastructure
sudo chown -R $USER:$USER /opt/resolvemeq-infrastructure
```

### 8.2 Create Nginx Configuration

```bash
nano /opt/resolvemeq-infrastructure/nginx.conf
```

**Replace `YOUR_DOMAIN` with your actual domain** and paste:

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 2048;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general_limit:10m rate=100r/s;

    # Upstream servers
    upstream django_backend {
        server resolvemeq-web-1:8000 max_fails=3 fail_timeout=30s;
    }

    upstream agent_backend {
        server resolvemeq-agent-prod:8000 max_fails=3 fail_timeout=30s;
    }

    # HTTP server - redirect to HTTPS
    server {
        listen 80;
        server_name YOUR_DOMAIN www.YOUR_DOMAIN;

        # Certbot challenge
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Redirect to HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name YOUR_DOMAIN www.YOUR_DOMAIN;

        # SSL certificates
        ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem;

        # SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Strict-Transport-Security "max-age=31536000" always;

        # Static files
        location /static/ {
            alias /var/www/static/;
            expires 30d;
        }

        # Media files
        location /media/ {
            alias /var/www/media/;
            expires 7d;
        }

        # Agent API
        location /agent/ {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://agent_backend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 120s;
            proxy_read_timeout 120s;
        }

        # Django API
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://django_backend/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Django admin
        location /admin/ {
            limit_req zone=general_limit burst=50 nodelay;
            
            proxy_pass http://django_backend/admin/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }

        # Root
        location / {
            limit_req zone=general_limit burst=50 nodelay;
            
            proxy_pass http://django_backend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

**Important:** Replace all instances of `YOUR_DOMAIN` with your actual domain.

Save and exit.

### 8.3 Create Docker Compose for Infrastructure

```bash
nano /opt/resolvemeq-infrastructure/docker-compose.yml
```

Paste:

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: resolvemeq-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - resolvemeq_static_files:/var/www/static:ro
      - resolvemeq_media_files:/var/www/media:ro
      - certbot_data:/etc/letsencrypt:ro
      - certbot_www:/var/www/certbot:ro
    networks:
      - resolvemeq-shared
    depends_on:
      - certbot

  certbot:
    image: certbot/certbot:latest
    container_name: resolvemeq-certbot
    volumes:
      - certbot_data:/etc/letsencrypt
      - certbot_www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
    restart: unless-stopped

networks:
  resolvemeq-shared:
    external: true

volumes:
  resolvemeq_static_files:
    external: true
  resolvemeq_media_files:
    external: true
  certbot_data:
    name: resolvemeq_certbot_data
  certbot_www:
    name: resolvemeq_certbot_www
```

Save and exit.

### 8.4 Obtain SSL Certificate

```bash
# First, start nginx temporarily for HTTP only
cd /opt/resolvemeq-infrastructure

# Modify nginx.conf to remove SSL temporarily
nano nginx.conf
```

Comment out the HTTPS server block (lines starting with `server {` for port 443) or simply run:

```bash
# Start a temporary nginx for certbot
docker run --rm -d \
  --name nginx-temp \
  -p 80:80 \
  -v $(pwd)/certbot_www:/var/www/certbot \
  nginx:alpine

# Create certbot www directory
mkdir -p certbot_www

# Request certificate (replace with your details)
docker run --rm \
  -v $(pwd)/certbot_data:/etc/letsencrypt \
  -v $(pwd)/certbot_www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@YOUR_DOMAIN \
  --agree-tos \
  --no-eff-email \
  -d YOUR_DOMAIN \
  -d www.YOUR_DOMAIN

# Stop temporary nginx
docker stop nginx-temp
```

### 8.5 Start Nginx with SSL

```bash
cd /opt/resolvemeq-infrastructure

# Start infrastructure
docker compose up -d

# Check status
docker compose ps

# Check logs
docker compose logs -f nginx
```

**✅ Nginx is now running with SSL!**

---

## Step 9: Verify Everything Works

### 9.1 Check All Containers

```bash
# Django services
docker ps --filter "name=resolvemeq-web"
docker ps --filter "name=resolvemeq-celery"

# Agent service
docker ps --filter "name=resolvemeq-agent"

# Nginx
docker ps --filter "name=resolvemeq-nginx"

# All should show "Up" status
```

### 9.2 Test Public Endpoints

```bash
# Health check
curl https://YOUR_DOMAIN/health

# Django API
curl https://YOUR_DOMAIN/api/tickets/analytics/

# Agent docs
curl https://YOUR_DOMAIN/agent/docs

# Admin panel (in browser)
# Visit: https://YOUR_DOMAIN/admin/
```

### 9.3 Test from Browser

1. **Admin Panel**: `https://YOUR_DOMAIN/admin/`
   - Login with superuser credentials
   
2. **API Documentation**: `https://YOUR_DOMAIN/agent/docs`
   - Should show FastAPI Swagger UI
   
3. **Health Check**: `https://YOUR_DOMAIN/health`
   - Should return "OK"

---

## Step 10: Post-Deployment Setup

### 10.1 Setup Automatic Updates (Optional)

Install Watchtower to auto-update containers:

```bash
docker run -d \
  --name watchtower \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower \
  --interval 300 \
  --cleanup
```

### 10.2 Setup Monitoring

```bash
# View logs
docker compose -f /opt/resolvemeq/docker-compose.yml logs -f

# View resource usage
docker stats

# Setup log rotation
sudo nano /etc/docker/daemon.json
```

Add:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:

```bash
sudo systemctl restart docker

# Restart all services
cd /opt/resolvemeq && docker compose up -d
cd /opt/resolvemeq-agent && docker compose up -d
cd /opt/resolvemeq-infrastructure && docker compose up -d
```

### 10.3 Setup Backups

Create backup script:

```bash
sudo nano /usr/local/bin/backup-resolvemeq.sh
```

Paste:

```bash
#!/bin/bash
BACKUP_DIR="/backup/resolvemeq"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec resolvemeq-db-1 pg_dump -U resolvemeq_user resolvemeq_prod > $BACKUP_DIR/db_$DATE.sql

# Backup media files
tar -czf $BACKUP_DIR/media_$DATE.tar.gz /var/lib/docker/volumes/resolvemeq_media_files

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

Make executable:

```bash
sudo chmod +x /usr/local/bin/backup-resolvemeq.sh
```

Add to crontab (daily at 2 AM):

```bash
sudo crontab -e
```

Add line:

```
0 2 * * * /usr/local/bin/backup-resolvemeq.sh
```

---

## 📊 Useful Commands

### Check Service Status

```bash
# Django
cd /opt/resolvemeq && docker compose ps

# Agent
cd /opt/resolvemeq-agent && docker compose ps

# Nginx
cd /opt/resolvemeq-infrastructure && docker compose ps
```

### View Logs

```bash
# Django web
docker logs -f resolvemeq-web-1

# Django celery worker
docker logs -f resolvemeq-celery_worker-1

# Agent
docker logs -f resolvemeq-agent-prod

# Nginx
docker logs -f resolvemeq-nginx
```

### Restart Services

```bash
# Restart Django
cd /opt/resolvemeq && docker compose restart web

# Restart Agent
cd /opt/resolvemeq-agent && docker compose restart agent

# Restart Nginx
cd /opt/resolvemeq-infrastructure && docker compose restart nginx

# Restart everything
cd /opt/resolvemeq && docker compose restart
cd /opt/resolvemeq-agent && docker compose restart
cd /opt/resolvemeq-infrastructure && docker compose restart
```

### Update to New Version

```bash
# Pull latest images
cd /opt/resolvemeq && docker compose pull
cd /opt/resolvemeq-agent && docker compose pull

# Restart with new images
cd /opt/resolvemeq && docker compose up -d
cd /opt/resolvemeq-agent && docker compose up -d

# Run migrations if needed
docker exec resolvemeq-web-1 python manage.py migrate
docker exec resolvemeq-web-1 python manage.py collectstatic --noinput
```

### Database Management

```bash
# Access PostgreSQL
docker exec -it resolvemeq-db-1 psql -U resolvemeq_user -d resolvemeq_prod

# Create database backup
docker exec resolvemeq-db-1 pg_dump -U resolvemeq_user resolvemeq_prod > backup.sql

# Restore database
cat backup.sql | docker exec -i resolvemeq-db-1 psql -U resolvemeq_user -d resolvemeq_prod
```

### Access Redis

```bash
# Access Redis CLI
docker exec -it resolvemeq-redis-1 redis-cli -a YOUR_REDIS_PASSWORD

# Check keys
KEYS *

# Monitor commands
MONITOR
```

---

## 🔧 Troubleshooting

### Issue: Django can't connect to database

```bash
# Check database is running
docker ps | grep postgres

# Check database logs
docker logs resolvemeq-db-1

# Verify credentials in .env file
cat /opt/resolvemeq/.env | grep DB_

# Test connection from Django container
docker exec resolvemeq-web-1 python manage.py dbshell
```

### Issue: Agent can't reach Django

```bash
# Check network
docker network inspect resolvemeq-shared

# Both resolvemeq-web-1 and resolvemeq-agent-prod should be listed

# Test from agent
docker exec resolvemeq-agent-prod curl http://resolvemeq-web-1:8000/api/tickets/analytics/
```

### Issue: Nginx showing 502 Bad Gateway

```bash
# Check backend services are running
docker ps | grep resolvemeq-web
docker ps | grep resolvemeq-agent

# Check Nginx logs
docker logs resolvemeq-nginx

# Verify Nginx can reach backends
docker exec resolvemeq-nginx ping resolvemeq-web-1
docker exec resolvemeq-nginx ping resolvemeq-agent-prod
```

### Issue: SSL certificate error

```bash
# Check certificate files
docker exec resolvemeq-nginx ls -la /etc/letsencrypt/live/YOUR_DOMAIN/

# Renew certificate manually
docker compose -f /opt/resolvemeq-infrastructure/docker-compose.yml exec certbot certbot renew

# Restart Nginx
docker restart resolvemeq-nginx
```

### Issue: Out of disk space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a --volumes

# Remove old images
docker image prune -a

# Check volume sizes
docker system df -v
```

---

## 🎉 Deployment Complete!

Your ResolveMeQ platform is now live at:
- **Main Site**: `https://YOUR_DOMAIN/`
- **Admin Panel**: `https://YOUR_DOMAIN/admin/`
- **API**: `https://YOUR_DOMAIN/api/`
- **Agent Docs**: `https://YOUR_DOMAIN/agent/docs`

### Next Steps:

1. ✅ Test all functionality thoroughly
2. ✅ Setup monitoring (Sentry, uptime monitors)
3. ✅ Configure email settings for notifications
4. ✅ Setup regular backups
5. ✅ Document your custom configurations
6. ✅ Train your team on the platform

---

## 📞 Support

If you encounter issues:
1. Check logs: `docker compose logs -f`
2. Review troubleshooting section above
3. Check GitHub Issues
4. Review documentation in `docs/` folder

**Congratulations on deploying ResolveMeQ! 🚀**
