# AI Agent API - Quick Reference

Fast lookup guide for all agent-related endpoints.

---

## 🚀 Core Agent Endpoints

### Trigger Agent Processing
```http
POST /api/tickets/{ticket_id}/process/
```
**Body (optional):**
```json
{ "reset": true }
```
**Response:**
```json
{ "task_id": "...", "status": "queued" }
```

---

### Get Agent Status
```http
GET /api/tickets/{ticket_id}/agent-status/
```
**Response:**
```json
{
  "agent_processed": true,
  "agent_response": {
    "confidence": 0.85,
    "recommended_action": "auto_resolve",
    "solution": { "steps": [...], "estimated_time": "10 min" }
  }
}
```

---

### Get AI Recommendations
```http
GET /api/tickets/agent/recommendations/
```
**Response:**
```json
{
  "recommendations": [
    {
      "ticket_id": 42,
      "recommendations": [
        {
          "type": "high_confidence_solution",
          "action": "auto_resolve",
          "confidence": 0.85
        }
      ]
    }
  ]
}
```

---

### Get AI Suggestions for Ticket
```http
GET /api/tickets/{ticket_id}/ai-suggestions/
```
**Response:**
```json
{
  "ai_suggestions": {
    "suggested_solution": "...",
    "confidence": 0.85,
    "similar_tickets": [...],
    "kb_articles": [...]
  }
}
```

---

## 📊 Monitoring & Analytics

### Agent Analytics
```http
GET /api/tickets/agent/analytics/
```
**Response:**
```json
{
  "total_tickets": 1250,
  "processed_by_agent": 1100,
  "agent_processing_rate": 88.0,
  "resolution_success_rate": 76.5,
  "average_confidence_score": 0.812
}
```

---

### Task Status
```http
GET /api/tickets/tasks/{task_id}/status/
```
**Response:**
```json
{
  "task_id": "...",
  "status": "SUCCESS",  // PENDING, STARTED, SUCCESS, FAILURE, RETRY
  "result": {...}
}
```

---

## 🕒 Action History & Rollback

### Action History
```http
GET /api/tickets/{ticket_id}/action-history/
```
**Response:**
```json
{
  "action_history": [
    {
      "id": "uuid",
      "action_type": "AUTO_RESOLVE",
      "executed_at": "2026-03-04T12:00:00Z",
      "confidence_score": 0.85,
      "rollback_possible": true,
      "rolled_back": false
    }
  ]
}
```

---

### Rollback Action
```http
POST /api/tickets/actions/{action_history_id}/rollback/
```
**Body:**
```json
{ "reason": "User reported issue persists" }
```
**Response:**
```json
{
  "message": "Action rolled back successfully",
  "rollback_details": {...}
}
```
**Permissions:** Admin/Manager only
**Rate Limit:** 5 per hour

---

## 💬 Feedback & Learning

### Submit Resolution Feedback
```http
POST /api/tickets/{ticket_id}/resolution-feedback/
```
**Body:**
```json
{
  "rating": 5,
  "was_helpful": true,
  "resolution_time_acceptable": true,
  "accuracy_rating": 5,
  "completeness_rating": 4,
  "clarity_rating": 5,
  "comments": "Great solution!",
  "would_recommend": true
}
```

---

### Resolution Analytics
```http
GET /api/tickets/resolution-analytics/
```
**Response:**
```json
{
  "total_resolutions": 850,
  "average_rating": 4.2,
  "helpfulness_rate": 0.85,
  "recommendation_rate": 0.78
}
```

---

## 🔍 Knowledge Base

### Enhanced KB Search
```http
POST /api/tickets/agent/kb-search/
```
**Body:**
```json
{
  "query": "email sync issue",
  "max_results": 5,
  "min_relevance": 0.7
}
```
**Response:**
```json
{
  "results": [
    {
      "id": "kb-123",
      "title": "...",
      "relevance_score": 0.92
    }
  ]
}
```

---

### KB Articles for Agent
```http
GET /api/knowledge_base/api/articles/
```
**Query Params:**
- `category`: Filter by category
- `limit`: Max results (default 10)

---

## 🎯 Quick Integration

### Check if Ticket Has Agent Analysis
```javascript
const hasAnalysis = ticket.agent_processed;
const confidence = ticket.agent_response?.confidence;
```

### Determine UI Action Based on Confidence
```javascript
if (confidence >= 0.8) {
  // Show "Accept Solution" button
} else if (confidence >= 0.6) {
  // Show "Review Suggestion" 
} else {
  // Show "Request Clarification"
}
```

### Agent Action Types
- `AUTO_RESOLVE` - High confidence solution
- `ESCALATE` - Critical or complex issue
- `REQUEST_CLARIFICATION` - Need more info
- `ASSIGN_TO_TEAM` - Route to specific team
- `SCHEDULE_FOLLOWUP` - Medium confidence, check later
- `CREATE_KB_ARTICLE` - Document new solution

---

## 🔑 Response Fields Reference

### Agent Response Structure
```typescript
interface AgentResponse {
  confidence: number;              // 0.0 - 1.0
  recommended_action: string;      // Action type
  analysis: {
    category: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    complexity: 'low' | 'medium' | 'high';
    suggested_team?: string;
  };
  solution: {
    steps: string[];
    estimated_time: string;
    success_probability: number;   // 0.0 - 1.0
  };
  reasoning: string;
}
```

---

## 🚦 Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 403 | Forbidden (permission) |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Server Error |
| 503 | Agent Unavailable |

---

## ⚡ Rate Limits

| Endpoint | Limit |
|----------|-------|
| Process ticket | 10/min per user |
| Rollback | 5/hour per user |
| Recommendations | 30/min (global) |
| Analytics | 60/min (global) |

---

## 🎨 UI Component Mapping

| Endpoint | UI Component |
|----------|--------------|
| `/process/` | "Get AI Help" button |
| `/agent-status/` | Agent status indicator |
| `/recommendations/` | Recommendations dashboard |
| `/ai-suggestions/` | Similar tickets sidebar |
| `/action-history/` | Action timeline |
| `/rollback/` | Undo button |
| `/resolution-feedback/` | Feedback form |

---

## 🔄 Polling Pattern

When triggering agent processing:

```javascript
// 1. Trigger
const { task_id } = await POST('/process/');

// 2. Poll every 2 seconds
const interval = setInterval(async () => {
  const { status } = await GET(`/tasks/${task_id}/status/`);
  
  if (status === 'SUCCESS' || status === 'FAILURE') {
    clearInterval(interval);
    // Update UI
  }
}, 2000);
```

---

## 🎯 Common Workflows

### Workflow 1: User Gets AI Help
```
1. POST /tickets/{id}/process/
2. Poll GET /tasks/{task_id}/status/
3. GET /tickets/{id}/agent-status/
4. Display suggestion with confidence
5. User accepts → Execute action
6. POST /tickets/{id}/resolution-feedback/
```

### Workflow 2: Admin Reviews Recommendations
```
1. GET /tickets/agent/recommendations/
2. Display list of suggested actions
3. Click on ticket → GET /tickets/{id}/ai-suggestions/
4. Review and accept/reject
5. Track in action history
```

### Workflow 3: Rollback Incorrect Action
```
1. GET /tickets/{id}/action-history/
2. Find action to rollback
3. POST /tickets/actions/{action_id}/rollback/
4. Provide reason
5. Ticket status restored
```

---

## 🧪 Testing Endpoints

### Sample cURL Commands

```bash
# Trigger agent processing
curl -X POST https://api.resolvemeq.net/api/tickets/42/process/ \
  -H "Authorization: Bearer $TOKEN"

# Get recommendations
curl https://api.resolvemeq.net/api/tickets/agent/recommendations/ \
  -H "Authorization: Bearer $TOKEN"

# Submit feedback
curl -X POST https://api.resolvemeq.net/api/tickets/42/resolution-feedback/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "was_helpful": true}'
```

---

## 📝 TypeScript Definitions

```typescript
// Agent Status Response
interface AgentStatusResponse {
  ticket_id: number;
  agent_processed: boolean;
  agent_response: AgentResponse | null;
  active_tasks: Task[];
  last_updated: string;
}

// Recommendation
interface Recommendation {
  ticket_id: number;
  issue_type: string;
  description: string;
  category: string;
  status: string;
  created_at: string;
  recommendations: RecommendationItem[];
}

interface RecommendationItem {
  type: 'high_confidence_solution' | 'suggested_solution' | 'similar_tickets';
  message: string;
  action: string;
  confidence?: number;
  similar_count?: number;
}

// Action History
interface ActionHistory {
  id: string;
  action_type: string;
  executed_at: string;
  executed_by: string;
  confidence_score: number;
  rollback_possible: boolean;
  rolled_back: boolean;
  rolled_back_at: string | null;
  rollback_reason: string | null;
}
```

---

## 🎨 Confidence Badge Component

```jsx
function ConfidenceBadge({ confidence }) {
  const config = {
    high: { color: 'green', label: 'High Confidence', min: 0.8 },
    medium: { color: 'yellow', label: 'Medium Confidence', min: 0.6 },
    low: { color: 'red', label: 'Low Confidence', min: 0 }
  };

  const level = confidence >= 0.8 ? 'high' 
              : confidence >= 0.6 ? 'medium' 
              : 'low';

  return (
    <span className={`badge-${config[level].color}`}>
      {config[level].label} ({(confidence * 100).toFixed(0)}%)
    </span>
  );
}
```

---

## 🚨 Error Handling

```javascript
try {
  const response = await fetch(endpoint, options);
  const data = await response.json();
  
  if (!response.ok) {
    switch (response.status) {
      case 403:
        toast.error('Permission denied');
        break;
      case 429:
        toast.error('Rate limit exceeded');
        break;
      case 503:
        toast.error('AI Agent temporarily unavailable');
        break;
      default:
        toast.error(data.error || 'An error occurred');
    }
  }
  
  return data;
} catch (error) {
  console.error('Agent API Error:', error);
  throw error;
}
```

---

## 📞 Support

- Full Documentation: [AGENT_API.md](./AGENT_API.md)
- API Explorer: https://api.resolvemeq.net/swagger
- Support: support@resolvemeq.net

---

**Last Updated:** March 4, 2026
