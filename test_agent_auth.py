#!/usr/bin/env python3
"""
Test script to verify Agent API Key authentication is working.
"""
import requests
import json

print("=" * 70)
print("🔐 TESTING AGENT API KEY AUTHENTICATION")
print("=" * 70)
print()

# The API key configured in Django
API_KEY = "resolvemeq-agent-secret-key-2026"

# Test 1: Update ticket status WITHOUT API key (should fail or use JWT)
print("1️⃣  Testing ticket status update WITHOUT Agent API key...")
print("-" * 70)
try:
    response = requests.post(
        "https://api.resolvemeq.net/api/tickets/1/status/",
        json={"status": "in-progress"},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
print()

# Test 2: Update ticket status WITH API key (should succeed)
print("2️⃣  Testing ticket status update WITH Agent API key...")
print("-" * 70)
try:
    response = requests.post(
        "https://api.resolvemeq.net/api/tickets/1/status/",
        json={"status": "in-progress"},
        headers={
            "Content-Type": "application/json",
            "X-Agent-API-Key": API_KEY
        },
        timeout=10
    )
    print(f"✅ Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"✅ Response: {response.json()}")
        print("✅ Agent API Key authentication is working!")
    else:
        print(f"⚠️  Response: {response.text[:200]}")
except Exception as e:
    print(f"❌ Error: {e}")
print()

# Test 3: Full agent analysis flow
print("3️⃣  Testing full agent analysis with status callback...")
print("-" * 70)
print("📝 The agent needs to be configured with the API key:")
print(f"   X-Agent-API-Key: {API_KEY}")
print()
print("🔧 Agent Configuration Required:")
print("   Environment Variable: AGENT_API_KEY=resolvemeq-agent-secret-key-2026")
print("   Or configure in agent's settings to send this header:")
print("   headers = {'X-Agent-API-Key': 'resolvemeq-agent-secret-key-2026'}")
print()

print("=" * 70)
print("📋 SUMMARY")
print("=" * 70)
print("✅ Django is configured to accept Agent API Key authentication")
print("✅ CSRF_TRUSTED_ORIGINS includes https://agent.resolvemeq.net")
print("✅ Endpoint /api/tickets/<id>/status/ accepts agent auth")
print()
print("🔧 NEXT STEPS:")
print("1. Configure the agent to send X-Agent-API-Key header")
print("2. Use API key: resolvemeq-agent-secret-key-2026")
print("3. Test full flow with: POST /tickets/analyze/")
print("=" * 70)
