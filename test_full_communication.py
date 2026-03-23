#!/usr/bin/env python3
"""
Smoke test: Agent + Django production (or override via env).

- Django: uses public GET /health/ (not /api/tickets/analytics/, which requires auth).
- Agent AI step: OpenAI quota / rate limits are treated as SKIP so CI does not fail
  on provider billing. Set STRICT_LIVE_AGENT_AI=1 to fail if suggest is not HTTP 200
  (including quota/rate-limit responses).

Env:
  DJANGO_API_BASE   default https://api.resolvemeq.net
  AGENT_API_BASE    default https://agent.resolvemeq.net
  STRICT_LIVE_AGENT_AI  if "1"/"true"/"yes", any non-200 suggest (incl. quota) fails the run
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import requests

DJANGO_API_BASE = os.getenv("DJANGO_API_BASE", "https://api.resolvemeq.net").rstrip("/")
AGENT_API_BASE = os.getenv("AGENT_API_BASE", "https://agent.resolvemeq.net").rstrip("/")
STRICT_LIVE_AGENT_AI = os.getenv("STRICT_LIVE_AGENT_AI", "").lower() in ("1", "true", "yes")

failures: list[str] = []
warnings: list[str] = []


def _is_provider_quota_response(response: requests.Response) -> bool:
    if response.status_code == 429:
        return True
    text = response.text.lower()
    return "quota" in text or "rate limit" in text or "exceeded your current quota" in text


print("=" * 70)
print("🔄 RESOLVEMEQ COMMUNICATION TEST")
print("=" * 70)
print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Django base: {DJANGO_API_BASE}")
print(f"Agent base:  {AGENT_API_BASE}")
print()

# Test 1: Agent Health Check
print("1️⃣  Testing Agent Health...")
print("-" * 70)
try:
    response = requests.get(f"{AGENT_API_BASE}/health", timeout=10)
    if response.status_code == 200:
        health = response.json()
        print(f"✅ Agent Status: {health.get('status', 'unknown')}")
        print(f"   Version: {health.get('version', 'unknown')}")
        print(f"   Environment: {health.get('environment', 'unknown')}")
        print(f"   Django KB URL: {health.get('services', {}).get('django_kb_url', 'N/A')}")
    else:
        print(f"❌ Health check failed: {response.status_code}")
        failures.append("agent_health")
except Exception as e:
    print(f"❌ Error: {e}")
    failures.append("agent_health")
print()

# Test 2: Django API (public health — analytics requires JWT)
print("2️⃣  Testing Django API...")
print("-" * 70)
try:
    response = requests.get(f"{DJANGO_API_BASE}/health/", timeout=10)
    if response.status_code == 200:
        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {}
        print("✅ Django API is accessible (public /health/)")
        print(f"   Payload: {data}")
    else:
        print(f"❌ Django API failed: {response.status_code}")
        failures.append("django_api")
except Exception as e:
    print(f"❌ Error: {e}")
    failures.append("django_api")
print()

# Test 3: Agent Suggestion (depends on upstream LLM quota)
print("3️⃣  Testing Agent AI Processing (Suggestion Mode)...")
print("-" * 70)
test_ticket = {
    "ticket_id": 999,
    "issue_type": "Email client not syncing",
    "description": (
        "My Outlook keeps showing 'Working Offline' and won't sync new emails. "
        "I've tried restarting but it doesn't help."
    ),
    "category": "email",
    "tags": ["outlook", "email", "sync"],
    "user": {
        "id": "test-user-123",
        "name": "Test User",
        "department": "Sales",
    },
}

agent_suggest_ok = False
try:
    print(f"📤 Sending ticket: {test_ticket['issue_type']}")
    response = requests.post(
        f"{AGENT_API_BASE}/tickets/suggest/",
        json=test_ticket,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )

    if response.status_code == 200:
        result = response.json()
        solution = result.get("solution", "")
        agent_suggest_ok = True
        print("✅ Agent Response Received!")
        print(f"   Response Length: {len(solution)} characters")
        print()
        print("📋 AI-Generated Solution (first 500 chars):")
        print("-" * 70)
        print((solution[:500] + "...") if len(solution) > 500 else solution)
        print("-" * 70)
    elif _is_provider_quota_response(response):
        msg = (
            "⚠️  Agent suggest skipped: provider quota or rate limit "
            f"(HTTP {response.status_code}). Not treated as a hard failure."
        )
        print(msg)
        if STRICT_LIVE_AGENT_AI:
            failures.append("agent_suggest_quota")
        else:
            warnings.append("agent_suggest_quota")
    else:
        print(f"❌ Agent failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        failures.append("agent_suggest")
except Exception as e:
    print(f"❌ Error: {e}")
    failures.append("agent_suggest")
print()

# Test 4: Check Agent Metrics
print("4️⃣  Testing Agent Metrics...")
print("-" * 70)
try:
    response = requests.get(f"{AGENT_API_BASE}/tickets/metrics", timeout=10)
    if response.status_code == 200:
        metrics = response.json()
        print("✅ Agent Metrics Retrieved")
        print(f"   Total Requests: {metrics.get('total_requests', 0)}")
        if "cache_hit_rate" in metrics:
            print(f"   Cache Hit Rate: {metrics.get('cache_hit_rate', 0):.1%}")
        else:
            print("   Cache: N/A")
    else:
        print(f"⚠️  Metrics: {response.status_code}")
        warnings.append("agent_metrics")
except Exception as e:
    print(f"⚠️  Error: {e}")
    warnings.append("agent_metrics")
print()

# Summary
print("=" * 70)
print("📊 TEST SUMMARY")
print("=" * 70)
agent_health_ok = "agent_health" not in failures
django_ok = "django_api" not in failures
print(f"{'✅' if agent_health_ok else '❌'} Agent Health Check")
print(f"{'✅' if django_ok else '❌'} Django API (/health/)")
if agent_suggest_ok:
    print("✅ Agent AI Processing (suggest)")
elif "agent_suggest_quota" in warnings:
    print("⚠️  Agent AI Processing (suggest): SKIPPED (provider quota / rate limit)")
elif "agent_suggest_quota" in failures:
    print("❌ Agent AI Processing (suggest): quota (STRICT_LIVE_AGENT_AI)")
elif "agent_suggest" in failures:
    print("❌ Agent AI Processing (suggest)")
else:
    print("⚠️  Agent AI Processing (suggest): unknown state")
print()
if warnings:
    print("Warnings:", ", ".join(warnings))
if failures:
    print("Failures:", ", ".join(failures))
print()
print("ℹ️  Authenticated endpoints (e.g. /api/tickets/analytics/) need a JWT; use /health/ for smoke tests.")
print("ℹ️  Set STRICT_LIVE_AGENT_AI=1 to fail the run unless /tickets/suggest/ returns 200.")
print("=" * 70)

sys.exit(1 if failures else 0)
