# Frontend AI Chat Integration Guide

## ✅ Backend Implementation Complete

I've implemented all the backend endpoints you need for real AI chat functionality. No more mock responses needed!

---

## 🎯 Available Endpoints

### 1. **Send Chat Message (Main Endpoint)**

```typescript
POST /api/tickets/{ticket_id}/chat/

// Request
{
  "message": "My printer is showing offline",
  "conversation_id": "uuid-here" // Optional: omit to start new conversation
}

// Response
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_message": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "sender_type": "user",
    "message_type": "text",
    "text": "My printer is showing offline",
    "created_at": "2026-03-04T12:34:56Z"
  },
  "ai_message": {
    "id": "234e5678-e89b-12d3-a456-426614174111",
    "sender_type": "ai",
    "message_type": "text", // Can be: text, steps, solution, question
    "text": "I can help you with that. Let me check a few things...",
    "confidence": 0.85,
    "metadata": {
      "suggested_actions": [
        "Check printer power",
        "Verify network connection"
     ],
      "quick_replies": [
        {"label": "Show solutions", "value": "Show me the solutions"},
        {"label": "Talk to human", "value": "Connect me with support"}
      ]
    },
    "created_at": "2026-03-04T12:34:57Z"
  }
}
```

### 2. **Get Conversation History**

```typescript
GET /api/tickets/{ticket_id}/chat/history/

// Response
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "ticket": 123,
  "messages": [
    {
      "id": "...",
      "sender_type": "user",
      "text": "Previous message",
      "created_at": "2026-03-04T12:00:00Z"
    },
    {
      "id": "...",
      "sender_type": "ai",
      "text": "AI response",
      "confidence": 0.9,
      "metadata": {...},
      "created_at": "2026-03-04T12:00:01Z"
    }
  ],
  "message_count": 10,
  "created_at": "2026-03-04T11:00:00Z",
  "resolved": false
}
```

### 3. **Submit Feedback** upload

```typescript
POST /api/tickets/{ticket_id}/chat/{message_id}/feedback/

// Request
{
  "rating": "helpful", // or "not_helpful"
  "comment": "This solved my problem!" // Optional
}

// Response
{
  "message": "Feedback submitted successfully",
  "message_id": "234e5678-e89b-12d3-a456-426614174111",
  "was_helpful": true
}
```

### 4. **Get Suggested Questions**

```typescript
GET /api/tickets/{ticket_id}/chat/suggestions/

// Response
{
  "suggestions": [
    {
      "id": "...",
      "label": "How do I reset my password?",
      "message_text": "I need help resetting my password",
      "category": "access"
    },
    {
      "id": "...",
      "label": "Printer is offline",
      "message_text": "My printer shows as offline",
      "category": "printer"
    }
  ],
  "ticket_id": 123,
  "category": "printer"
}
```

---

## 🚀 Frontend Implementation

### Replace Mock Response with Real API

**Before (Mock - DON'T DO THIS):**
```javascript
const generateAIResponse = (userMessage) => {
  return {
    id: Date.now(),
    type: 'ai',
    message: 'Mock response...',  // ❌ Fake!
  };
};
```

**After (Real AI - DO THIS):**
```javascript
import { api } from '@/services/api';

const sendMessageToAI = async (messageText) => {
  // Add user message to UI
  setAiMessages((prev) => [...prev, {
    id: `temp-${Date.now()}`,
    type: 'user',
    message: messageText,
  }]);
  
  setIsAiTyping(true);
  
  try {
    // REAL API CALL 🎉
    const response = await api.post(
      `/tickets/${currentTicket.id}/chat/`,
      {
        message: messageText,
        conversation_id: conversationId // Save this from first response
      }
    );
    
    // Save conversation ID for next messages
    if (response.data.conversation_id) {
      setConversationId(response.data.conversation_id);
    }
    
    // Add AI response to UI
    const aiMsg = response.data.ai_message;
    setAiMessages((prev) => [...prev, {
      id: aiMsg.id,
      type: 'ai',
      message: aiMsg.text,
      confidence: aiMsg.confidence,
      suggestions: aiMsg.metadata?.suggested_actions || [],
      choices: aiMsg.metadata?.quick_replies || [],
      messageType: aiMsg.message_type,
    }]);
    
  } catch (error) {
    console.error('Chat error:', error);
    // Show error message
    setAiMessages((prev) => [...prev, {
      id: `error-${Date.now()}`,
      type: 'system',
      message: 'Sorry, I had trouble processing that. Please try again.',
    }]);
  } finally {
    setIsAiTyping(false);
  }
};
```

---

## 📝 Complete React Example

```jsx
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import { ThumbsUp, ThumbsDown, Sparkles } from 'lucide-react';

export function AIChat Assistant({ ticket }) {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [inputText, setInputText] = useState('');
  
  // Load conversation history on mount
  useEffect(() => {
    loadHistory();
  }, [ticket.id]);
  
  const loadHistory = async () => {
    try {
      const { data } = await api.get(`/tickets/${ticket.id}/chat/history/`);
      if (data.id) {
        setConversationId(data.id);
        setMessages(data.messages.map(msg => ({
          id: msg.id,
          type: msg.sender_type,
          text: msg.text,
          confidence: msg.confidence,
          metadata: msg.metadata,
          wasHelpful: msg.was_helpful,
        })));
      }
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };
  
  const sendMessage = async () => {
    if (!inputText.trim()) return;
    
    const userMsg = {
      id: `temp-${Date.now()}`,
      type: 'user',
      text: inputText,
    };
    
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsTyping(true);
    
    try {
      const { data } = await api.post(`/tickets/${ticket.id}/chat/`, {
        message: inputText,
        conversation_id: conversationId,
      });
      
      // Save conversation ID
      if (!conversationId) {
        setConversationId(data.conversation_id);
      }
      
      // Add AI response
      const aiMsg = data.ai_message;
      setMessages(prev => [...prev, {
        id: aiMsg.id,
        type: aiMsg.sender_type,
        text: aiMsg.text,
        confidence: aiMsg.confidence,
        metadata: aiMsg.metadata,
        messageType: aiMsg.message_type,
      }]);
      
    } catch (error) {
      console.error('Send error:', error);
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        type: 'system',
        text: 'Failed to send message. Please try again.',
      }]);
    } finally {
      setIsTyping(false);
    }
  };
  
  const submitFeedback = async (messageId, helpful) => {
    try {
      await api.post(
        `/tickets/${ticket.id}/chat/${messageId}/feedback/`,
        {
          rating: helpful ? 'helpful' : 'not_helpful'
        }
      );
      
      // Update UI
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, wasHelpful: helpful }
          : msg
      ));
    } catch (error) {
      console.error('Feedback error:', error);
    }
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(msg => (
          <div key={msg.id}>
            {msg.type === 'ai' ? (
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1">
                  <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
                    <p className="text-sm">{msg.text}</p>
                    
                    {/* Confidence badge */}
                    {msg.confidence && (
                      <div className="mt-2">
                        <ConfidenceBadge confidence={msg.confidence} />
                      </div>
                    )}
                    
                    {/* Quick replies */}
                    {msg.metadata?.quick_replies && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {msg.metadata.quick_replies.map((reply, idx) => (
                          <button
                            key={idx}
                            onClick={() => setInputText(reply.value)}
                            className="px-3 py-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-full text-xs hover:bg-gray-50"
                          >
                            {reply.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  {/* Feedback buttons */}
                  {msg.wasHelpful === null && (
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-xs text-gray-500">Was this helpful?</span>
                      <button
                        onClick={() => submitFeedback(msg.id, true)}
                        className="p-1 hover:bg-green-50 dark:hover:bg-green-900/20 rounded"
                      >
                        <ThumbsUp className="w-3.5 h-3.5 text-gray-400 hover:text-green-600" />
                      </button>
                      <button
                        onClick={() => submitFeedback(msg.id, false)}
                        className="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                      >
                        <ThumbsDown className="w-3.5 h-3.5 text-gray-400 hover:text-red-600" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex justify-end">
                <div className="bg-primary-600 text-white rounded-lg p-3 max-w-[80%]">
                  <p className="text-sm">{msg.text}</p>
                </div>
              </div>
            )}
          </div>
        ))}
        
        {/* Typing indicator */}
        {isTyping && (
          <div className="flex items-center gap-2 text-gray-500">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span className="text-xs">AI is typing...</span>
          </div>
        )}
      </div>
      
      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-800 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Type your message..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={sendMessage}
            disabled={!inputText.trim() || isTyping}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

// Confidence badge component
function ConfidenceBadge({ confidence }) {
  const getColor = () => {
    if (confidence >= 0.8) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    if (confidence >= 0.6) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
  };
  
  const getLabel = () => {
    if (confidence >= 0.8) return 'High Confidence';
    if (confidence >= 0.6) return 'Medium Confidence';
    return 'Low Confidence';
  };
  
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getColor()}`}>
      {getLabel()} ({Math.round(confidence * 100)}%)
    </span>
  );
}
```

---

## 🎨 Message Types

The AI can send different message types. Handle them in your UI:

```jsx
{msg.messageType === 'steps' && (
  <div className="space-y-2 mt-3">
    <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
      Follow these steps:
    </p>
    {msg.metadata.steps?.map((step, idx) => (
      <div key={idx} className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-900 rounded">
        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary-600 text-white text-xs flex items-center justify-center">
          {idx + 1}
        </span>
        <span className="text-sm">{step}</span>
      </div>
    ))}
  </div>
)}

{msg.messageType === 'solution' && (
  <div className="mt-3">
    <button
      onClick={() => applySolution(msg)}
      className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
    >
      Apply This Solution
    </button>
  </div>
)}
```

---

## 🔗 Integration with Existing Agent Processing

You can combine the chat with the existing agent processing endpoint:

```typescript
// Check if ticket has agent analysis
const {data: agentStatus} = await api.get(`/tickets/${ticketId}/agent-status/`);

if (agentStatus.agent_processed) {
  // Show agent analysis in chat
  setMessages(prev => [...prev, {
    type: 'system',
    text: `AI has already analyzed this ticket with ${Math.round(agentStatus.confidence * 100)}% confidence.`,
    metadata: {
      quick_replies: [
        {label: 'Show analysis', value: 'Show me the full analysis'},
        {label: 'Ask a question', value: 'I have a question about this'},
      ]
    }
  }]);
}
```

---

## 📱 Mobile Optimization

For mobile, use a bottom sheet instead of modal:

```jsx
// Use libraries like react-spring-bottom-sheet
import BottomSheet from 'react-spring-bottom-sheet';
import 'react-spring-bottom-sheet/dist/style.css';

<BottomSheet
  open={showChat}
  onDismiss={() => setShowChat(false)}
  snapPoints={({ maxHeight }) => [
    maxHeight * 0.4,  // Quarter screen
    maxHeight * 0.7,  // Most of screen
    maxHeight * 0.95, // Almost full screen
  ]}
  defaultSnap={({ snapPoints }) => snapPoints[1]}
>
  <AIChat ticket={ticket} />
</BottomSheet>
```

---

## ✅ Checklist for Frontend Developer

- [ ] Remove all mock response code
- [ ] Implement `sendMessage()` with real API
- [ ] Add conversation ID state management
- [ ] Load conversation history on mount
- [ ] Implement feedback buttons (thumbs up/down)
- [ ] Show confidence badges on AI messages
- [ ] Render quick reply buttons from metadata
- [ ] Handle different message types (text, steps, solution)
- [ ] Add typing indicator
- [ ] Test on mobile (bottom sheet recommended)
- [ ] Add error handling for network failures
- [ ] Persist conversation across page refreshes

---

## 🚨 Common Issues & Solutions

### Issue: "Conversation not persisting"
**Solution:** Save `conversation_id` from first response and pass it in subsequent requests.

```javascript
// First message - no conversation_id
const response1 = await api.post('/tickets/123/chat/', {
  message: "Hello"
});
const convId = response1.data.conversation_id; // Save this!

// Second message - include conversation_id
const response2 = await api.post('/tickets/123/chat/', {
  message: "Follow up question",
  conversation_id: convId // ✅ Include it
});
```

### Issue: "Messages not showing metadata"
**Solution:** Check `ai_message.metadata` field in response:

```javascript
const aiMsg = response.data.ai_message;
const quickReplies = aiMsg.metadata?.quick_replies || [];
const suggestedActions = aiMsg.metadata?.suggested_actions || [];
```

### Issue: "Confidence not rendering"
**Solution:** It's a float between 0.0 and 1.0. Convert to percentage:

```javascript
const confidencePercent = Math.round(aiMsg.confidence * 100);
// Display: "85% confident"
```

---

## 📞 Need Help?

Check these docs:
- [AGENT_API.md](./AGENT_API.md) - Full agent API reference
- [AGENT_API_QUICK_REFERENCE.md](./AGENT_API_QUICK_REFERENCE.md) - Quick examples
- [MARKETING_API.md](./MARKETING_API.md) - Newsletter/contact endpoints

The chat endpoints are now LIVE and ready to use! No more mock responses needed. 🎉
