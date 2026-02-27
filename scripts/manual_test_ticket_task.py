import os
import django
from tickets.tasks import process_ticket_with_agent

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resolvemeq.settings')
django.setup()

def test_ticket_processing():
    print("Testing ticket processing task...")
    
    # Replace this with an actual ticket ID from your database
    test_ticket_id = "your_ticket_id_here"
    
    try:
        # Send the task
        result = process_ticket_with_agent.delay(test_ticket_id)
        print(f"✓ Task sent successfully. Task ID: {result.id}")
        
        # Wait for result
        task_result = result.get(timeout=30)
        print(f"✓ Task completed with result: {task_result}")
    except Exception as e:
        print(f"✗ Failed to process ticket: {str(e)}")

if __name__ == '__main__':
    test_ticket_processing() 