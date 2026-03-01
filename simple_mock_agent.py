#!/usr/bin/env python3
"""
Simple mock AI agent using Python's built-in HTTP server.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class MockAgentHandler(BaseHTTPRequestHandler):
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/tickets/analyze/' or self.path == '/api/analyze':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                print("=" * 60)
                print("📨 Received ticket for analysis:")
                print(f"   Ticket ID: {data.get('ticket_id')}")
                print(f"   Issue: {data.get('issue_type', 'N/A')}")
                print(f"   Category: {data.get('category', 'N/A')}")
                print(f"   User: {data.get('user', {}).get('name', 'N/A')}")
                print("=" * 60)
                
                # Mock response
                response = {
                    "confidence": 0.87,
                    "recommended_action": "auto_resolve",
                    "analysis": {
                        "category": data.get('category', 'general'),
                        "severity": "medium",
                        "complexity": "low",
                        "suggested_team": "IT Support"
                    },
                    "solution": {
                        "steps": [
                            "Restart the VPN service",
                            "Check network settings",
                            "Verify credentials"
                        ],
                        "estimated_time": "10 minutes",
                        "success_probability": 0.87
                    },
                    "reasoning": f"Common {data.get('category', 'general')} issue with known solution"
                }
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
                print("✅ Sent response back!")
                print()
                
            except Exception as e:
                self.send_error(500, f"Error: {str(e)}")
        else:
            self.send_error(404, "Not found")
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode('utf-8'))
        elif self.path == '/docs':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Mock AI Agent</h1><p>POST /tickets/analyze/</p>")
        else:
            self.send_error(404, "Not found")
    
    def log_message(self, format, *args):
        """Custom log format."""
        return  # Suppress default logging

if __name__ == '__main__':
    server_address = ('', 8001)
    httpd = HTTPServer(server_address, MockAgentHandler)
    
    print("=" * 60)
    print("🤖 Mock AI Agent Server Started")
    print("=" * 60)
    print("   URL: http://localhost:8001")
    print("   Endpoint: POST /tickets/analyze/")
    print("   Health: GET /health")
    print("=" * 60)
    print()
    print("Waiting for requests...")
    print()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        httpd.shutdown()
