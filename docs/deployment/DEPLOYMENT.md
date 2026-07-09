# ResolveMeQ Deployment Guide

## Production Requirements

### 1. System Requirements
- Python 3.8+
- Redis 6+
- PostgreSQL 12+ (recommended) or your preferred database
- Nginx (recommended) or Apache
- Systemd (for service management)

### 2. Required Python Packages
Add these to your `requirements.txt`:
```
gunicorn==21.2.0
psycopg2-binary==2.9.10  # For PostgreSQL
dj-database-url==3.0.0
whitenoise==6.6.0  # For static files
```

### 3. Production Settings
Create a `production.py` in your settings directory:

```python
from .base import *

DEBUG = False
SECRET_KEY = os.getenv('SECRET_KEY')

# Security settings
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS]
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600
    )
}

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Redis and Celery
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
```

## Deployment Steps

### 1. Database Setup
```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE resolvemeq;
CREATE USER resolvemeq WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE resolvemeq TO resolvemeq;
```

### 2. Redis Setup
```bash
# Install Redis
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 3. Application Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic

# Run migrations
python manage.py migrate
```

### 4. Gunicorn Setup
Create `/etc/systemd/system/resolvemeq.service`:
```ini
[Unit]
Description=ResolveMeQ Gunicorn Service
After=network.target

[Service]
User=your-user
Group=your-group
WorkingDirectory=/path/to/resolvemeq
Environment="PATH=/path/to/resolvemeq/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=resolvemeq.settings"
ExecStart=/path/to/resolvemeq/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/path/to/resolvemeq/resolvemeq.sock \
    resolvemeq.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 5. Celery Setup
Create `/etc/systemd/system/resolvemeq-celery.service`:
```ini
[Unit]
Description=ResolveMeQ Celery Service
After=network.target

[Service]
User=your-user
Group=your-group
WorkingDirectory=/path/to/resolvemeq
Environment="PATH=/path/to/resolvemeq/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=resolvemeq.settings"
ExecStart=/path/to/resolvemeq/venv/bin/celery -A resolvemeq worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/resolvemeq-celerybeat.service`:
```ini
[Unit]
Description=ResolveMeQ Celery Beat Service
After=network.target

[Service]
User=your-user
Group=your-group
WorkingDirectory=/path/to/resolvemeq
Environment="PATH=/path/to/resolvemeq/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=resolvemeq.settings"
ExecStart=/path/to/resolvemeq/venv/bin/celery -A resolvemeq beat -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

### 6. Nginx Setup
Create `/etc/nginx/sites-available/resolvemeq`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /path/to/resolvemeq;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/resolvemeq/resolvemeq.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
}
```

### 7. Start Services
```bash
# Enable and start services
sudo systemctl enable resolvemeq
sudo systemctl start resolvemeq
sudo systemctl enable resolvemeq-celery
sudo systemctl start resolvemeq-celery
sudo systemctl enable resolvemeq-celerybeat
sudo systemctl start resolvemeq-celerybeat

# Enable and start Nginx
sudo ln -s /etc/nginx/sites-available/resolvemeq /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## Monitoring

### 1. Service Status
```bash
# Check service status
sudo systemctl status resolvemeq
sudo systemctl status resolvemeq-celery
sudo systemctl status resolvemeq-celerybeat
sudo systemctl status nginx
sudo systemctl status redis-server
```

### 2. Logs
```bash
# View logs
sudo journalctl -u resolvemeq
sudo journalctl -u resolvemeq-celery
sudo journalctl -u resolvemeq-celerybeat
sudo tail -f /var/log/nginx/error.log
```

### 3. Celery Monitoring
```bash
# Monitor Celery tasks
python manage.py manage_agent_tasks --action list
python manage.py manage_agent_tasks --action stats
```

## Backup

### 1. Database Backup
```bash
# Create backup script
#!/bin/bash
BACKUP_DIR="/path/to/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump -U resolvemeq resolvemeq > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
```

### 2. Redis Backup
```bash
# Redis persistence is enabled by default
# Backup RDB file
sudo cp /var/lib/redis/dump.rdb /path/to/backups/redis_$(date +%Y%m%d_%H%M%S).rdb
```

## Security Checklist

- [ ] Set DEBUG=False
- [ ] Use strong SECRET_KEY
- [ ] Configure ALLOWED_HOSTS
- [ ] Enable SSL/TLS
- [ ] Set up proper database permissions
- [ ] Configure firewall (UFW)
- [ ] Set up regular backups
- [ ] Enable Redis password
- [ ] Configure proper file permissions
- [ ] Set up monitoring and alerts 