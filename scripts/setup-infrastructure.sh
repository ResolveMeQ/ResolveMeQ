# ResolveMeQ VPS Infrastructure Setup Script
# This script sets up the infrastructure layer (Nginx + SSL) for production

set -e  # Exit on error

echo "=================================================="
echo " ResolveMeQ VPS Infrastructure Setup"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
INFRASTRUCTURE_DIR="/opt/resolvemeq-infrastructure"
DOMAIN="${1:-}"

# Check if domain provided
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Error: Domain name required${NC}"
    echo "Usage: $0 your-domain.com"
    exit 1
fi

echo -e "${YELLOW}Setting up infrastructure for: $DOMAIN${NC}"

# 1. Create infrastructure directory
echo -e "\n${GREEN}[1/6]${NC} Creating infrastructure directory..."
sudo mkdir -p $INFRASTRUCTURE_DIR
cd $INFRASTRUCTURE_DIR

# 2. Create shared Docker network (if not exists)
echo -e "\n${GREEN}[2/6]${NC} Creating shared Docker network..."
if ! docker network inspect resolvemeq-shared >/dev/null 2>&1; then
    docker network create resolvemeq-shared
    echo "✓ Created resolvemeq-shared network"
else
    echo "✓ Network resolvemeq-shared already exists"
fi

# 3. Download/create nginx configuration
echo -e "\n${GREEN}[3/6]${NC} Creating Nginx configuration..."
cat > nginx.conf << 'EOF'
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
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general_limit:10m rate=100r/s;

    # Upstream servers
    upstream django_backend {
        server resolvemeq-web-1:8000 max_fails=3 fail_timeout=30s;
        # Add more Django instances here for load balancing
        # server resolvemeq-web-2:8000 max_fails=3 fail_timeout=30s;
    }

    upstream agent_backend {
        server resolvemeq-agent-prod:8000 max_fails=3 fail_timeout=30s;
    }

    # HTTP server - redirect to HTTPS
    server {
        listen 80;
        server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

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
        server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

        # SSL certificates (replace after obtaining cert)
        ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;

        # SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Static files
        location /static/ {
            alias /var/www/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }

        # Media files
        location /media/ {
            alias /var/www/media/;
            expires 7d;
            add_header Cache-Control "public";
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
            proxy_send_timeout 120s;
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
            
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
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

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }

        # Default - serve Django frontend or redirect
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
EOF

# Replace domain placeholder
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx.conf
echo "✓ Created nginx.conf"

# 4. Create docker-compose file
echo -e "\n${GREEN}[4/6]${NC} Creating docker-compose configuration..."
cat > docker-compose.yml << 'EOF'
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
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 10s
      retries: 3

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
EOF
echo "✓ Created docker-compose.yml"

# 5. Obtain SSL certificate
echo -e "\n${GREEN}[5/6]${NC} Obtaining SSL certificate..."
echo -e "${YELLOW}Starting Nginx temporarily for Certbot challenge...${NC}"

# Start nginx without SSL first
docker run --rm -d \
  --name nginx-certbot-temp \
  -p 80:80 \
  -v $INFRASTRUCTURE_DIR/certbot_www:/var/www/certbot \
  nginx:alpine \
  sh -c "mkdir -p /var/www/certbot && nginx -g 'daemon off;'"

# Request certificate
docker run --rm \
  -v $INFRASTRUCTURE_DIR/certbot_data:/etc/letsencrypt \
  -v $INFRASTRUCTURE_DIR/certbot_www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@$DOMAIN \
  --agree-tos \
  --no-eff-email \
  -d $DOMAIN \
  -d www.$DOMAIN

# Stop temporary nginx
docker stop nginx-certbot-temp || true

echo "✓ SSL certificate obtained"

# 6. Start infrastructure
echo -e "\n${GREEN}[6/6]${NC} Starting infrastructure services..."
docker compose up -d

echo -e "\n${GREEN}=================================================="
echo " Infrastructure Setup Complete!"
echo "==================================================${NC}"
echo ""
echo "Services:"
echo "  • Nginx: running on ports 80, 443"
echo "  • Certbot: auto-renewal enabled"
echo ""
echo "Next steps:"
echo "  1. Ensure Django backend is running:"
echo "     cd /opt/resolvemeq && docker compose -f docker-compose.production.yml ps"
echo "  2. Ensure Agent is running:"
echo "     cd /opt/resolvemeq-agent && docker compose -f docker-compose.production.yml ps"
echo "  3. Test your domain:"
echo "     https://$DOMAIN/health"
echo "     https://$DOMAIN/api/tickets/analytics/"
echo "     https://$DOMAIN/agent/docs"
echo ""
echo "Logs:"
echo "  docker logs -f resolvemeq-nginx"
echo ""
