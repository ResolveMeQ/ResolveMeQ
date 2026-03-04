#!/bin/bash

# ResolveMeQ Celery Setup Script for VPS
# Run this on your VPS to configure Celery worker as a systemd service

set -e  # Exit on error

echo "=== ResolveMeQ Celery Worker Setup ==="
echo

# Variables - CHANGE THESE to match your VPS paths
PROJECT_PATH="/var/www/resolvemeq"
VENV_PATH="${PROJECT_PATH}/venv"
SERVICE_USER="www-data"
SERVICE_GROUP="www-data"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

echo "✓ Running as root"

# Check if project exists
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Project path not found: $PROJECT_PATH"
    echo "   Please update PROJECT_PATH in this script"
    exit 1
fi

echo "✓ Project found at $PROJECT_PATH"

# Check if virtual environment exists
if [ ! -f "$VENV_PATH/bin/celery" ]; then
    echo "❌ Celery not found in virtualenv"
    echo "   Install it with: $VENV_PATH/bin/pip install celery redis"
    exit 1
fi

echo "✓ Celery found in virtualenv"

# Create log directories
echo
echo "Creating log directories..."
mkdir -p /var/log/celery
mkdir -p /var/run/celery
chown ${SERVICE_USER}:${SERVICE_GROUP} /var/log/celery
chown ${SERVICE_USER}:${SERVICE_GROUP} /var/run/celery
echo "✓ Log directories created"

# Copy systemd service file
echo
echo "Installing systemd service..."
cp ${PROJECT_PATH}/resolvemeq-celery.service /etc/systemd/system/resolvemeq-celery.service

# Update paths in service file if needed
sed -i "s|/var/www/resolvemeq|${PROJECT_PATH}|g" /etc/systemd/system/resolvemeq-celery.service
sed -i "s|User=www-data|User=${SERVICE_USER}|g" /etc/systemd/system/resolvemeq-celery.service
sed -i "s|Group=www-data|Group=${SERVICE_GROUP}|g" /etc/systemd/system/resolvemeq-celery.service

echo "✓ Service file installed"

# Reload systemd
echo
echo "Reloading systemd daemon..."
systemctl daemon-reload
echo "✓ Systemd reloaded"

# Enable service to start on boot
echo
echo "Enabling service to start on boot..."
systemctl enable resolvemeq-celery
echo "✓ Service enabled"

# Start the service
echo
echo "Starting Celery worker..."
systemctl start resolvemeq-celery

# Wait a moment for service to start
sleep 2

# Check status
echo
echo "=== Service Status ==="
systemctl status resolvemeq-celery --no-pager

# Show available commands
echo
echo "=== Setup Complete ==="
echo
echo "Useful commands:"
echo "  Start:   sudo systemctl start resolvemeq-celery"
echo "  Stop:    sudo systemctl stop resolvemeq-celery"
echo "  Restart: sudo systemctl restart resolvemeq-celery"
echo "  Status:  sudo systemctl status resolvemeq-celery"
echo "  Logs:    sudo journalctl -u resolvemeq-celery -f"
echo
echo "To check if worker is processing tasks:"
echo "  cd $PROJECT_PATH"
echo "  source venv/bin/activate"
echo "  celery -A resolvemeq inspect active"
echo
