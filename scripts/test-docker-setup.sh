#!/bin/bash

# Local Docker Deployment Test Script
# Tests the Docker setup locally before deploying to VPS

set -e

echo "🧪 Testing ResolveMeQ Docker Setup"
echo "==================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env not found. Creating from .env.example...${NC}"
    cp .env.example .env
    echo "✅ Created .env from .env.example"
    echo "⚠️  Please review and update .env with your settings"
fi

# Build images
echo -e "${GREEN}[1/6] Building Docker images...${NC}"
docker compose build --no-cache

# Start services
echo -e "${GREEN}[2/6] Starting services...${NC}"
docker compose up -d

# Wait for services to be healthy
echo -e "${GREEN}[3/6] Waiting for services to be healthy...${NC}"
sleep 10

# Check database
echo -e "${GREEN}[4/6] Running migrations...${NC}"
docker compose exec -T web python manage.py migrate --noinput

# Collect static files
echo -e "${GREEN}[5/6] Collecting static files...${NC}"
docker compose exec -T web python manage.py collectstatic --noinput --clear

# Health checks
echo -e "${GREEN}[6/6] Running health checks...${NC}"

echo ""
echo "🔍 Container Status:"
docker compose ps

echo ""
echo "🔍 Health Checks:"

# Check Django
if curl -f -s http://localhost:8000/api/tickets/analytics/ > /dev/null; then
    echo -e "  ✅ Django Web: ${GREEN}Healthy${NC}"
else
    echo -e "  ❌ Django Web: ${RED}Failed${NC}"
fi

# Check Agent
if curl -f -s http://localhost:8001/docs > /dev/null; then
    echo -e "  ✅ AI Agent: ${GREEN}Healthy${NC}"
else
    echo -e "  ❌ AI Agent: ${RED}Failed${NC}"
fi

# Check Database
if docker compose exec -T db pg_isready -U resolvemeq > /dev/null; then
    echo -e "  ✅ PostgreSQL: ${GREEN}Healthy${NC}"
else
    echo -e "  ❌ PostgreSQL: ${RED}Failed${NC}"
fi

# Check Redis
if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "  ✅ Redis: ${GREEN}Healthy${NC}"
else
    echo -e "  ❌ Redis: ${RED}Failed${NC}"
fi

echo ""
echo "📊 Service URLs:"
echo "  - Django Admin: http://localhost:8000/admin"
echo "  - API Docs: http://localhost:8000/api/docs"
echo "  - Agent API: http://localhost:8001/docs"
echo ""
echo "📝 Useful Commands:"
echo "  - View logs: docker compose logs -f"
echo "  - Stop services: docker compose down"
echo "  - Restart service: docker compose restart web"
echo "  - Create superuser: docker compose exec web python manage.py createsuperuser"
echo ""
echo -e "${GREEN}✅ Docker setup test complete!${NC}"
