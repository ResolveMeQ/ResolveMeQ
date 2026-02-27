# VPS Management & Domain Setup Guide

## 1. Daily VPS Management

### Check Service Status
```bash
docker compose ps
```

### View Logs
```bash
docker compose logs -f web
# For agent:
docker compose logs -f agent
```

### Restart Services
```bash
docker compose restart web
# For agent:
docker compose restart agent
```

### Update to Latest Images
```bash
docker compose pull
docker compose up -d
```

### Run Migrations & Collect Static Files
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

### Create Django Superuser
```bash
docker compose exec web python manage.py createsuperuser
```

---

## 2. Configuring Your Domain Name

### Step 1: Register a Domain
- Use a provider like Namecheap, GoDaddy, Google Domains, etc.

### Step 2: Point Domain to VPS
- In your domain provider’s dashboard, set an A record for your domain (e.g., `yourdomain.com`) to your VPS public IP.

### Step 3: Update ALLOWED_HOSTS
- In your `.env` file, add your domain to `ALLOWED_HOSTS`:
  ```
  ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,YOUR_VPS_IP
  ```
- Restart Django:
  ```bash
  docker compose restart web
  ```

### Step 4: Configure Nginx for SSL
- Update Nginx config to use your domain.
- Use Certbot to obtain SSL certificates:
  ```bash
  sudo apt install certbot
  sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
  ```
- Update Nginx config to use the new certificates and restart Nginx.

---

## 3. Security & Backups

### Enable UFW Firewall
```bash
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Regular Backups
- Backup database and media files regularly (see deployment guide for scripts).

---

## 4. Monitoring & Maintenance

### Monitor Resource Usage
```bash
docker stats
```

### Error Monitoring
- Sentry is already configured in your `.env`.

### Log Rotation & Automatic Updates
- Set up log rotation and Watchtower for auto-updates (see deployment guide).

---

## 5. Troubleshooting

- **502 Bad Gateway:** Check if backend containers are running and healthy.
- **SSL Issues:** Renew certificates with Certbot and restart Nginx.
- **Database Issues:** Check logs and credentials in `.env`.

---

## 6. When You Get a Domain

1. Update DNS A record to point to your VPS IP.
2. Update `.env` and Nginx config with your domain.
3. Obtain and configure SSL certificates.
4. Restart all services.

---

## 7. Useful Commands

### Access Django Admin
```bash
http://YOUR_VPS_IP:8000/admin/
```

### Access API Endpoints
```bash
http://YOUR_VPS_IP:8000/api/tickets/analytics/
http://YOUR_VPS_IP:8000/health
http://YOUR_VPS_IP:8001/docs
```

---

## 8. Next Steps
- Test all functionality thoroughly
- Setup monitoring (Sentry, uptime monitors)
- Configure email settings for notifications
- Setup regular backups
- Document custom configurations
- Train your team on the platform

---

For more details, see your main deployment guide (VPS_DEPLOYMENT_STEP_BY_STEP.md).
