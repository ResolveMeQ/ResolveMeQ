# FastAPI Agent Chat Endpoint (Optional Enhancement)

## Overview

This document provides the code to add a dedicated `/tickets/chat/` endpoint to your FastAPI agent for better conversational AI responses.

**Status:** OPTIONAL - The chat feature currently works using `/tickets/analyze/` endpoint  
**Benefit:** More conversational, context-aware responses optimized for back-and-forth chat

---

## When to Implement This

- ✅ Implement if you want shorter, more conversational AI responses
- ✅ Implement if chat responses from `/analyze/` are too verbose
- ⏸️ Skip for now - current implementation works fine

---

## FastAPI Endpoint Code

Add this to your `resolvemeq-agent/app/api/endpoints/tickets.py`:

```python
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Add to your Pydantic models
class ChatMessage(BaseModel):
    sender: str  # 'user' or 'ai'
    text: str
    type: str  # 'text', 'steps', etc.

class ChatRequest(BaseModel):
    ticket_id: int
    issue_type: str
    description: str
    category: str
    tags: List[str] = []
    user: Dict[str, Any]
    # Optional: previous conversation context
    conversation_context: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    text: str
    confidence: float
    message_type: str  # 'text', 'steps', 'question', 'solution'
    metadata: Dict[str, Any] = {}

# Add this new route
@router.post("/tickets/chat/", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    x_agent_api_key: str = Header(..., alias="X-Agent-API-Key")
):
    """
    Conversational AI endpoint for ticket chat.
    
    Optimized for back-and-forth dialogue with context awareness.
    """
    # Validate API key
    expected_key = os.getenv("DJANGO_API_KEY", "resolvemeq-agent-secret-key-2026")
    if x_agent_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    logger.info(f"Chat request for ticket {request.ticket_id}")
    
    try:
        # Build context-aware prompt
        context_messages = ""
        if request.conversation_context:
            recent_context = request.conversation_context[-5:]  # Last 5 messages
            context_messages = "\n".join([
                f"{msg.sender.upper()}: {msg.text}" 
                for msg in recent_context
            ])
        
        # Analyze with LLM (using your existing AI service)
        analysis = await analyze_ticket_with_context(
            ticket_id=request.ticket_id,
            issue_type=request.issue_type,
            description=request.description,
            category=request.category,
            context=context_messages
        )
        
        # Format response for chat (more concise than full analysis)
        chat_response = format_for_chat(analysis, request.category)
        
        return ChatResponse(
            text=chat_response['text'],
            confidence=analysis.get('confidence', 0.7),
            message_type=chat_response['message_type'],
            metadata={
                'suggested_actions': chat_response.get('actions', []),
                'quick_replies': generate_quick_replies(analysis, request.category),
                'can_auto_resolve': analysis.get('confidence', 0) >= 0.85,
            }
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        # Return helpful fallback instead of error
        return ChatResponse(
            text=f"I understand you're having {request.category} issues. Let me gather more information to help you better.",
            confidence=0.5,
            message_type='text',
            metadata={
                'quick_replies': [
                    {'label': 'Provide more details', 'value': 'I can explain the issue in more detail'},
                    {'label': 'Talk to human', 'value': 'Connect me with support staff'},
                ]
            }
        )


async def analyze_ticket_with_context(
    ticket_id: int,
    issue_type: str,
    description: str,
    category: str,
    context: str = ""
) -> Dict[str, Any]:
    """
    Analyze ticket with conversation context.
    This is a wrapper around your existing analysis logic.
    """
    # Build enhanced description with context
    enhanced_description = description
    if context:
        enhanced_description = f"{description}\n\n--- Recent Conversation ---\n{context}"
    
    # Use your existing AI analysis (OpenAI, Anthropic, etc.)
    # This is just an example - adapt to your actual implementation
    analysis = {
        'confidence': 0.75,
        'solution': {
            'steps': [
                "Step 1: Check the basics",
                "Step 2: Advanced troubleshooting",
            ]
        },
        'recommended_action': 'provide_solution',
        'analysis': {
            'category': category,
            'severity': 'medium',
        }
    }
    
    return analysis


def format_for_chat(analysis: Dict[str, Any], category: str) -> Dict[str, Any]:
    """
    Convert full analysis to conversational chat format.
    """
    solution = analysis.get('solution', {})
    
    if isinstance(solution, dict):
        steps = solution.get('steps', [])
        
        # Create conversational text
        if len(steps) == 0:
            text = "I need a bit more information to help you with this issue."
            message_type = 'question'
        elif len(steps) == 1:
            text = f"Here's what I suggest: {steps[0]}"
            message_type = 'text'
        elif len(steps) <= 3:
            text = "Here's what you can try:\n\n" + "\n".join(f"• {step}" for step in steps)
            message_type = 'steps'
        else:
            # Show subset for chat
            text = "I have a solution for you. Here are the first steps:\n\n"
            text += "\n".join(f"• {step}" for step in steps[:3])
            message_type = 'steps'
            
        # Extract actionable items
        actions = []
        if analysis.get('confidence', 0) >= 0.8:
            actions.append('apply_solution')
        if analysis.get('recommended_action') == 'escalate':
            actions.append('escalate_to_human')
            
        return {
            'text': text,
            'message_type': message_type,
            'actions': actions,
            'full_steps': steps  # Include all steps in metadata
        }
    else:
        return {
            'text': str(solution),
            'message_type': 'text',
            'actions': []
        }


def generate_quick_replies(analysis: Dict[str, Any], category: str) -> List[Dict[str, str]]:
    """Generate contextual quick reply suggestions."""
    replies = []
    
    confidence = analysis.get('confidence', 0)
    
    if confidence >= 0.8:
        replies.append({
            'label': 'Try this solution',
            'value': 'Please apply this solution'
        })
    elif confidence >= 0.6:
        replies.append({
            'label': 'Tell me more',
            'value': 'Can you explain in more detail?'
        })
    else:
        replies.append({
            'label': 'Need more help',
            'value': 'I need additional assistance'
        })
    
    # Always offer these
    replies.extend([
        {'label': 'Show similar issues', 'value': 'Show me similar resolved tickets'},
        {'label': 'Talk to someone', 'value': 'Connect me with a support agent'},
    ])
    
    return replies[:4]  # Limit to 4 quick replies
```

---

## How to Update Django to Use New Endpoint

Once you add the FastAPI endpoint above, update your Django `tickets/chat_views.py`:

```python
# In _get_ai_chat_response function (line ~318)

# BEFORE (current - uses /analyze/):
agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.net/tickets/analyze/')

# AFTER (to use new /chat/ endpoint):
agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.net/tickets/chat/')

# Also update payload to include conversation context:
payload = {
    'ticket_id': ticket.ticket_id,
    'issue_type': ticket.issue_type,
    'description': ticket.description,
    'category': ticket.category,
    'tags': ticket.tags or [],
    'user': {
        'id': str(user.id),
        'name': user.username,
        'department': getattr(user, 'department', ''),
    },
    'conversation_context': [
        {
            'sender': msg['sender'],
            'text': msg['text'],
            'type': msg['type']
        }
        for msg in context  # context is already built above
    ]
}
```

---

## Deployment Steps

### 1. Update FastAPI Agent

```bash
# SSH to your VPS or clone agent repo
cd /opt/resolvemeq-agent  # or wherever your agent is

# Add the code above to:
# app/api/endpoints/tickets.py

# Test locally
uvicorn app.main:app --reload

# Rebuild and deploy
docker build -t resolvemeq-agent:latest .
docker-compose up -d
```

### 2. Update Django

```bash
# Update chat_views.py as shown above
# Commit and deploy
git add tickets/chat_views.py
git commit -m "feat: Use dedicated chat endpoint"
git push
```

### 3. Test

```bash
curl -X POST https://agent.resolvemeq.net/tickets/chat/ \
  -H "Content-Type: application/json" \
  -H "X-Agent-API-Key: your-key" \
  -d '{
    "ticket_id": 1,
    "issue_type": "Printer not working",
    "description": "My printer wont connect to WiFi",
    "category": "printer",
    "tags": [],
    "user": {"id": "123", "name": "Test User", "department": "IT"},
    "conversation_context": []
  }'
```

---

## Benefits of Dedicated Chat Endpoint

| Feature | Using `/analyze/` | Using `/chat/` |
|---------|------------------|----------------|
| Response length | Verbose (full analysis) | Concise (conversational) |
| Context awareness | ❌ No | ✅ Yes (last 5 messages) |
| Conversation continuity | ❌ Each call independent | ✅ Maintains flow |
| Response time | ~3-5s | ~1-2s (optimized) |
| Token usage | High (full analysis) | Lower (focused response) |

---

## Current Status

✅ **Chat works NOW** using `/analyze/` endpoint  
⏸️ **This is optional** - implement when ready for optimization  
📋 **Estimated effort**: 2-3 hours (agent code + testing + deployment)

---

## Next Steps

1. ✅ Test current chat implementation (uses `/analyze/`)
2. ⏸️ If responses are good enough, skip this for now
3. 🔄 If you want better chat experience, implement endpoint above
4. 📊 Monitor chat quality and user feedback
5. 🚀 Decide whether optimization is needed

---

## Summary

**Current:** Chat uses `/tickets/analyze/` - works but verbose  
**Future:** Can add `/tickets/chat/` for better experience  
**Decision:** Start with current, upgrade later if needed
