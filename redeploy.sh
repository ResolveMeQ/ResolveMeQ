#!/bin/bash
# Quick redeployment script for production

echo "🚀 Redeploying ResolveMeQ Backend..."

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Rebuild and restart containers
echo "🏗️  Rebuilding containers..."
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check container status
echo "📊 Container Status:"
docker-compose -f docker-compose.production.yml ps

# Check web logs
echo "📝 Recent Web Logs:"
docker-compose -f docker-compose.production.yml logs --tail=20 web

echo "✅ Deployment complete!"
echo "🔍 Test health endpoint: curl https://api.resolvemeq.net/api/monitoring/health/"
