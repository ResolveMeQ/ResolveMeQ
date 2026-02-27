import os
import django
from core.celery import app
from core.tasks import test_task

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resolvemeq.settings')
django.setup()

def test_celery_connection():
    print("Testing Celery connection...")
    
    # Test 1: Check broker connection
    try:
        with app.connection() as conn:
            conn.connect()
            print("✓ Successfully connected to broker")
    except Exception as e:
        print(f"✗ Failed to connect to broker: {str(e)}")
        return

    # Test 2: Send a test task
    try:
        result = test_task.delay()
        print(f"✓ Task sent successfully. Task ID: {result.id}")
        
        # Wait for result
        task_result = result.get(timeout=10)
        print(f"✓ Task completed with result: {task_result}")
    except Exception as e:
        print(f"✗ Failed to send/execute task: {str(e)}")

if __name__ == '__main__':
    test_celery_connection() 