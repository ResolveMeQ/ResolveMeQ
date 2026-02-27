# Utility Scripts

This directory contains utility scripts for deployment, setup, and manual testing.

## Deployment Scripts

### VPS Setup
- **vps-setup.sh** - Automated VPS preparation (Docker, firewall, SSH keys)
- **setup-infrastructure.sh** - Setup Nginx + SSL for production
- **test-docker-setup.sh** - Validate Docker setup locally

## Manual Testing Scripts

These scripts are for **manual testing only** and require actual services to be running. They are **not** part of the automated test suite.

### Prerequisites
All manual test scripts require:
- Running Django server
- Active database connection
- Configured environment variables

### Agent Testing
- **manual_test_agent.py** - Test FastAPI agent endpoint manually
  ```bash
  # Edit FASTAPI_URL in the file first
  python scripts/manual_test_agent.py
  ```

### Celery Testing
- **manual_test_celery.py** - Basic Celery task execution test
  ```bash
  # Requires Celery worker running
  python scripts/manual_test_celery.py
  ```

- **manual_test_celery_comprehensive.py** - Comprehensive Celery connection test
  ```bash
  python scripts/manual_test_celery_comprehensive.py
  ```

### Redis Testing
- **manual_test_redis.py** - Test Redis connection and operations
  ```bash
  # Configure redis_url in the file first
  python scripts/manual_test_redis.py
  ```

### Ticket Processing
- **manual_test_ticket_task.py** - Test ticket processing with agent
  ```bash
  # Update test_ticket_id in the file first
  python scripts/manual_test_ticket_task.py
  ```

## Usage Notes

⚠️ **Important**: These manual test scripts:
- Are **NOT** run by CI/CD pipelines
- Require actual infrastructure (Redis, Celery, Agent) to be running
- Should be run locally for debugging and verification
- Are excluded from automated test discovery

For automated tests, see:
- `test_autonomous_agent.py` - Autonomous agent tests
- `test_settings.py` - Settings configuration tests
- `tickets/test_new_features.py` - New features tests
- App-specific `tests.py` files in each Django app
