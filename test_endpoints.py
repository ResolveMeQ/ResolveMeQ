"""
Quick test script for new API endpoints
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resolvemeq.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

# Create test client
client = Client()

# Get or create a test user
User = get_user_model()
user = User.objects.first()
if not user:
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

# Login
client.force_login(user)

print("=" * 70)
print("API ENDPOINT TESTING")
print("=" * 70)

# Test 1: List Resolution Templates
print("\n1. GET /api/tickets/agent/templates/")
print("-" * 70)
response = client.get('/api/tickets/agent/templates/')
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Total templates: {len(data)}")
    if data:
        print(f"First template: {data[0]['name']}")
        print(f"  Category: {data[0]['category']}")
        print(f"  Estimated time: {data[0]['estimated_time']} min")
        print(f"  Use count: {data[0]['use_count']}")
else:
    print(f"Error: {response.content}")

# Test 2: Get Templates for Specific Ticket
print("\n2. GET /api/tickets/1/agent/templates/suggestions/")
print("-" * 70)
response = client.get('/api/tickets/1/agent/templates/suggestions/')
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Suggested templates: {len(data)}")
    if data:
        print(f"Top suggestion: {data[0]['name']}")
        print(f"  Category: {data[0]['category']}")
else:
    print(f"Error: {response.content}")

# Test 3: Dashboard Summary
print("\n3. GET /api/tickets/agent/dashboard-summary/")
print("-" * 70)
response = client.get('/api/tickets/agent/dashboard-summary/')
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Active tickets: {data.get('active_tickets', 0)}")
    print(f"Total tickets: {data.get('total_tickets', 0)}")
    print(f"Agent processed: {data.get('agent_processed_count', 0)}")
    print(f"Average confidence: {data.get('average_confidence', 0):.2f}%")
else:
    print(f"Error: {response.content}")

# Test 4: Confidence Explanation (only if ticket is processed)
from tickets.models import Ticket
ticket = Ticket.objects.filter(ticket_id=1).first()
if ticket and ticket.agent_processed:
    print("\n4. GET /api/tickets/1/agent/confidence-explanation/")
    print("-" * 70)
    response = client.get('/api/tickets/1/agent/confidence-explanation/')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Overall confidence: {data.get('confidence_score', 0):.2f}%")
        print(f"Factors analyzed: {len(data.get('factors', []))}")
        if data.get('factors'):
            print(f"Top factor: {data['factors'][0]['factor']}")
            print(f"  Impact: {data['factors'][0]['impact_percentage']}%")
    else:
        print(f"Error: {response.content}")
else:
    print("\n4. Confidence Explanation")
    print("-" * 70)
    print("Skipped - Ticket #1 not processed by agent yet")

# Test 5: Batch Operations Validation
print("\n5. POST /api/tickets/agent/validate-action/")
print("-" * 70)
response = client.post(
    '/api/tickets/agent/validate-action/',
    data=json.dumps({
        'ticket_id': 1,
        'action_type': 'status_change',
        'action_data': {'new_status': 'resolved'}
    }),
    content_type='application/json'
)
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Valid: {data.get('valid', False)}")
    if not data.get('valid'):
        print(f"Errors: {data.get('errors', [])}")
else:
    print(f"Error: {response.content}")

print("\n" + "=" * 70)
print("✅ ENDPOINT TESTING COMPLETE")
print("=" * 70)
