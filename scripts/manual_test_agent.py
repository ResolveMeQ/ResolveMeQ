import requests

# Replace with your actual FastAPI endpoint URL
FASTAPI_URL = "https://agent.resolvemeq.com/api/tickets/analyze/"

test_data = {
    "id": 4,
    "title": "Test Ticket",
    "description": "This is a test ticket for FastAPI integration.",
    "priority": "high",  
    "status": "new",   
    "created_at": "2024-06-09T12:00:00Z"  
}

response = requests.post(FASTAPI_URL, json=test_data)

print("Status code:", response.status_code)
print("Response body:", response.text)
