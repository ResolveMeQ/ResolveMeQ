#!/usr/bin/env python3
"""
Mock AI Agent Server for testing communication.
This simulates the FastAPI agent endpoint for local testing.
"""
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

@app.route('/tickets/analyze/', methods=['POST'])
def analyze_ticket():
    """Mock endpoint that simulates the AI agent analysis."""
    
    data = request.get_json()
    
    print("=" * 60)
    print("📨 Received ticket for analysis:")
    print(f"   Ticket ID: {data.get('ticket_id')}")
    print(f"   Issue: {data.get('issue_type')}")
    print(f"   Category: {data.get('category')}")
    print(f"   User: {data.get('user', {}).get('name')}")
    print("=" * 60)
    
    # Simulate agent response
    confidence = round(random.uniform(0.7, 0.95), 2)
    
    response = {
        "confidence": confidence,
        "recommended_action": "auto_resolve" if confidence > 0.85 else "assign_to_human",
        "analysis": {
            "category": data.get('category', 'general'),
            "severity": "medium",
            "complexity": "low" if confidence > 0.85 else "medium",
            "suggested_team": "IT Support"
        },
        "solution": {
            "steps": [
                "Step 1: Restart the service",
                "Step 2: Clear cache",
                "Step 3: Test connection"
            ],
            "estimated_time": "10 minutes",
            "success_probability": confidence
        },
        "reasoning": f"This is a common {data.get('category')} issue with known solutions. Confidence: {confidence}"
    }
    
    print("✅ Sending response back to Django...")
    return jsonify(response)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "Mock AI Agent"})

@app.route('/docs', methods=['GET'])
def docs():
    """Mock docs endpoint."""
    return """
    <html>
        <head><title>Mock AI Agent API</title></head>
        <body>
            <h1>Mock AI Agent API</h1>
            <p>This is a mock server for testing purposes.</p>
            <h2>Endpoints:</h2>
            <ul>
                <li>POST /tickets/analyze/ - Analyze a ticket</li>
                <li>GET /health - Health check</li>
            </ul>
        </body>
    </html>
    """

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 Starting Mock AI Agent Server")
    print("=" * 60)
    print("   URL: http://localhost:8001")
    print("   Endpoint: POST /tickets/analyze/")
    print("   Health: GET /health")
    print("=" * 60)
    print()
    app.run(host='0.0.0.0', port=8001, debug=True)
