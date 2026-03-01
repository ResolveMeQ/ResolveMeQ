#!/usr/bin/env python3
"""
Test script to directly communicate with the AI agent endpoint.
This bypasses Celery to test the agent communication directly.
"""
import requests
import json
from django.conf import settings
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resolvemeq.settings')
django.setup()

from tickets.models import Ticket

def test_agent_communication():
    """Test sending a ticket to the AI agent endpoint."""
    
    # Get agent URL from settings
    agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.net/tickets/analyze/')
    print(f"🔗 Agent URL: {agent_url}")
    print("-" * 60)
    
    # Get a test ticket
    try:
        ticket = Ticket.objects.first()
        if not ticket:
            print("❌ No tickets found in database")
            return
        
        print(f"📋 Testing with Ticket #{ticket.ticket_id}")
        print(f"   Issue: {ticket.description[:100]}...")
        print(f"   Category: {ticket.category}")
        print(f"   Status: {ticket.status}")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error fetching ticket: {e}")
        return
    
    # Prepare payload
    payload = {
        "ticket_id": ticket.ticket_id,
        "issue_type": ticket.issue_type,
        "description": ticket.description,
        "category": ticket.category,
        "tags": ticket.tags,
        "user": {
            "id": str(ticket.user.id),
            "name": ticket.user.username,
            "department": getattr(ticket.user, "department", "")
        }
    }
    
    print("📤 Sending payload to agent:")
    print(json.dumps(payload, indent=2))
    print("-" * 60)
    
    # Send request
    try:
        print("⏳ Sending POST request to agent...")
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            agent_url, 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        
        print(f"✅ Response Status: {response.status_code}")
        print("-" * 60)
        
        if response.status_code == 200:
            print("📥 Agent Response:")
            try:
                response_data = response.json()
                print(json.dumps(response_data, indent=2))
                print("-" * 60)
                print("✅ Communication successful!")
                
                # Check response structure
                if 'confidence' in response_data:
                    print(f"   Confidence: {response_data['confidence']}")
                if 'recommended_action' in response_data:
                    print(f"   Recommended Action: {response_data['recommended_action']}")
                if 'analysis' in response_data:
                    print(f"   Analysis: {response_data['analysis']}")
                    
            except json.JSONDecodeError:
                print("⚠️  Response is not valid JSON:")
                print(response.text[:500])
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: Cannot reach agent at {agent_url}")
        print(f"   Error: {e}")
        print("\n💡 Possible reasons:")
        print("   - Agent service is not running")
        print("   - Agent URL is incorrect")
        print("   - Network/firewall issues")
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout: Agent did not respond within 30 seconds")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 AI Agent Communication Test")
    print("=" * 60)
    test_agent_communication()
    print("=" * 60)
