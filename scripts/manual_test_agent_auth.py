#!/usr/bin/env python3
"""
Manual verification script for Agent API Key authentication.
Not part of the automated test suite — run directly with `python scripts/manual_test_agent_auth.py`.
Targets a real backend (defaults to production) and will mutate ticket state, so run deliberately.
"""
import os
import sys

import requests

API_KEY = os.environ.get("AGENT_API_KEY")
BASE_URL = os.environ.get("AGENT_AUTH_TEST_BASE_URL", "https://api.resolvemeq.net")
TICKET_ID = os.environ.get("AGENT_AUTH_TEST_TICKET_ID", "1")


def main():
    if not API_KEY:
        print("Set AGENT_API_KEY in the environment before running this script.")
        sys.exit(1)

    print("=" * 70)
    print("TESTING AGENT API KEY AUTHENTICATION")
    print(f"Target: {BASE_URL}  (ticket #{TICKET_ID})")
    print("=" * 70)
    print()

    print("1) Testing ticket status update WITHOUT Agent API key (expect 401/403)...")
    print("-" * 70)
    try:
        response = requests.post(
            f"{BASE_URL}/api/tickets/{TICKET_ID}/status/",
            json={"status": "in-progress"},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    print()

    print("2) Testing ticket status update WITH Agent API key (expect 200)...")
    print("-" * 70)
    try:
        response = requests.post(
            f"{BASE_URL}/api/tickets/{TICKET_ID}/status/",
            json={"status": "in-progress"},
            headers={
                "Content-Type": "application/json",
                "X-Agent-API-Key": API_KEY,
            },
            timeout=10,
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    print()

    print("Done. Remember: this mutated real ticket state if pointed at a live backend.")


if __name__ == "__main__":
    main()
