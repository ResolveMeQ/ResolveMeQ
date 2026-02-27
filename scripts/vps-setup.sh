#!/bin/bash

# VPS Setup Script for ResolveMeQ Deployment
# Run this script on your VPS to prepare for deployment

set -e

echo "🚀 ResolveMeQ VPS Setup Script"
echo "================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOY_PATH="/opt/resolvemeq"
DEPLOY_USER="${USER}"

echo -e "${YELLOW}📋 System Information:${NC}"
echo "  - OS: $(lsb_release -d | cut -f2-)"
echo "  - User: ${DEPLOY_USER}"
echo "  - Deploy Path: ${DEPLOY_PATH}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  Not running as root. Some commands may require sudo.${NC}"
fi

# 1. Update system
echo -e "${GREEN}[1/8] Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# 2. Install Docker
echo -e "${GREEN}[2/8] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ${DEPLOY_USER}
    rm get-docker.sh
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed"
fi

# 3. Install Docker Compose
echo -e "${GREEN}[3/8] Installing Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

# 4. Create deployment directory
echo -e "${GREEN}[4/8] Creating deployment directory...${NC}"
sudo mkdir -p ${DEPLOY_PATH}
sudo chown ${DEPLOY_USER}:${DEPLOY_USER} ${DEPLOY_PATH}
echo "✅ Directory created: ${DEPLOY_PATH}"

# 5. Configure firewall
echo -e "${GREEN}[5/8] Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    sudo ufw --force enable
    sudo ufw allow 22/tcp comment 'SSH'
    sudo ufw allow 80/tcp comment 'HTTP'
    sudo ufw allow 443/tcp comment 'HTTPS'
    sudo ufw status
    echo "✅ Firewall configured"
else
    echo "⚠️  UFW not found, skipping firewall configuration"
fi

# 6. Install useful tools
echo -e "${GREEN}[6/8] Installing useful tools...${NC}"
sudo apt install -y git curl wget htop certbot net-tools

# 7. Create environment file template
echo -e "${GREEN}[7/8] Creating environment file template...${NC}"
cd ${DEPLOY_PATH}
cat > .env.template << 'EOF'
# Production Environment Variables
# IMPORTANT: Fill in all CHANGE_ME values before deploying!

# Database Configuration
DB_NAME=resolvemeq_prod
DB_USER=resolvemeq_user
DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD

# Redis Configuration  
REDIS_PASSWORD=CHANGE_ME_REDIS_PASSWORD

# Django Configuration
SECRET_KEY=CHANGE_ME_50_CHARS_SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Sentry Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
ENVIRONMENT=production
APP_VERSION=1.0.0

# GitHub Container Registry
GITHUB_REPOSITORY_OWNER=your-github-username
IMAGE_TAG=latest
AGENT_IMAGE_TAG=latest

# Rate Limiting
AGENT_ACTION_RATE=50/m
ROLLBACK_RATE=10/h
USER_RATE=100/h
EOF

echo "✅ Environment template created at ${DEPLOY_PATH}/.env.template"

# 8. Generate SSH key for GitHub Actions (optional)
echo -e "${GREEN}[8/8] SSH key for GitHub Actions...${NC}"
read -p "Generate SSH key for GitHub Actions deployment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ ! -f ~/.ssh/github_deploy ]; then
        ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy -N ""
        cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
        echo ""
        echo "✅ SSH key generated!"
        echo "📋 Add this PRIVATE key to GitHub Secrets as VPS_SSH_PRIVATE_KEY:"
        echo "-------------------------------------------"
        cat ~/.ssh/github_deploy
        echo "-------------------------------------------"
    else
        echo "✅ SSH key already exists"
    fi
fi

echo ""
echo -e "${GREEN}✅ VPS Setup Complete!${NC}"
echo ""
echo "📝 Next Steps:"
echo "  1. Edit ${DEPLOY_PATH}/.env.template and save as ${DEPLOY_PATH}/.env"
echo "  2. Add VPS_SSH_PRIVATE_KEY to GitHub Secrets"
echo "  3. Add other secrets to GitHub repository settings"
echo "  4. Run 'Deploy to VPS' workflow from GitHub Actions"
echo ""
echo "🔍 Verify installation:"
echo "  docker --version"
echo "  docker-compose --version"
echo "  cd ${DEPLOY_PATH} && ls -la"
echo ""
echo "⚠️  NOTE: You may need to log out and back in for Docker group permissions to take effect."
