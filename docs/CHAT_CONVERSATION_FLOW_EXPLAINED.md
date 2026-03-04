# AI Chat Conversation Flow - Explained for Frontend

## 🎯 Overview: How Ticket Chat Works

**YES, users CAN have ongoing conversations with the AI for each ticket!**

Each ticket has its own **persistent conversation session** where:
- User sends messages → AI responds → User asks followup → AI responds → repeat until resolved
- All messages are saved in the database
- AI has context from previous messages in the conversation
- User can give feedback (thumbs up/down) on AI responses
- Conversation continues until ticket is resolved

---

## 🔄 Conversation Flow (Step by Step)

### 1️⃣ **User Creates/Opens a Ticket**
```
User: "My printer won't connect to WiFi"
→ Ticket #27 created with status="new"
```

### 2️⃣ **User Starts Chat on That Ticket**
```
Frontend calls:
POST /api/tickets/27/chat/
Body: { "message": "My printer won't connect to WiFi" }

Backend creates:
- Conversation (if first message)
- Saves user's ChatMessage
- Sends to AI agent with context
- AI responds with solution
- Saves AI's ChatMessage
- Returns both messages
```

### 3️⃣ **User Asks Followup Questions**
```
User: "I tried that but still not working. What else can I do?"

Frontend calls SAME endpoint:
POST /api/tickets/27/chat/
Body: { 
  "message": "I tried that but still not working...",
  "conversation_id": "abc-123..." 
}

Backend:
- Saves user's message to SAME conversation
- Gathers last 10 messages as context
- Sends to AI: "Here's what we discussed before, now user says..."
- AI provides next steps based on conversation history
- Saves AI response
- Returns messages
```

### 4️⃣ **This Continues Until Resolved**
```
User: "That worked! Thanks!"
→ AI: "Great! Would you like me to mark this ticket as resolved?"
→ User: "Yes please"
→ AI marks conversation.resolved = True
→ Ticket status updated to "resolved"
```

---

## 📊 Database Structure

```
Ticket #27 "Printer won't connect"
  └── Conversation (UUID: abc-123...)
        ├── ChatMessage 1 (user): "My printer won't connect"
        ├── ChatMessage 2 (ai): "Let's try these steps..."
        ├── ChatMessage 3 (user): "I tried that, didn't work"
        ├── ChatMessage 4 (ai): "Okay, next try this..."
        ├── ChatMessage 5 (user): "That worked!"
        └── ChatMessage 6 (ai): "Great! Mark as resolved?"
```

**Key Points:**
- **ONE conversation per ticket** (per user)
- **MANY messages** in that conversation
- Messages have `sender_type`: "user" | "ai" | "system"
- AI gets **context** from previous messages

---

## 🎨 Frontend Implementation Guide

### A. Load Conversation History When User Opens Ticket

```javascript
// When user clicks on ticket to view it
const loadTicketChat = async (ticketId) => {
  try {
    // Get all previous messages
    const { data } = await api.get(`/tickets/${ticketId}/chat/history/`);
    
    if (data.conversation) {
      setConversationId(data.conversation.id);
      setMessages(data.conversation.messages); // Array of all messages
    } else {
      // No conversation yet, will create on first message
      setMessages([]);
    }
  } catch (error) {
    console.error('Failed to load chat:', error);
  }
};
```

### B. Send New Message (User Types and Hits Send)

```javascript
const sendMessage = async (messageText) => {
  try {
    // Add user message to UI immediately (optimistic)
    const userMsg = {
      id: 'temp-' + Date.now(),
      sender_type: 'user',
      text: messageText,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    
    // Send to backend
    const { data } = await api.post(`/tickets/${ticketId}/chat/`, {
      message: messageText,
      conversation_id: conversationId // Include if exists
    });
    
    // Backend returns BOTH user message (saved) and AI response
    setConversationId(data.conversation_id);
    
    // Replace temp user msg with real one + add AI response
    setMessages(prev => [
      ...prev.filter(m => m.id !== userMsg.id),
      data.user_message,  // User's message (with real ID)
      data.ai_message     // AI's response
    ]);
    
  } catch (error) {
    console.error('Failed to send message:', error);
    // Remove optimistic message, show error
  }
};
```

### C. User Gives Feedback (Thumbs Up/Down)

```javascript
const submitFeedback = async (messageId, isHelpful) => {
  try {
    await api.post(`/tickets/${ticketId}/chat/${messageId}/feedback/`, {
      was_helpful: isHelpful,
      feedback_comment: '' // Optional
    });
    
    // Update UI to show feedback was recorded
    setMessages(prev => prev.map(msg => 
      msg.id === messageId 
        ? { ...msg, was_helpful: isHelpful }
        : msg
    ));
  } catch (error) {
    console.error('Failed to submit feedback:', error);
  }
};
```

### D. Complete React Component Example

```jsx
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import { ThumbsUp, ThumbsDown } from 'lucide-react';

export function TicketChat({ ticket }) {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Load conversation history when ticket opens
  useEffect(() => {
    loadHistory();
  }, [ticket.id]);
  
  const loadHistory = async () => {
    try {
      const { data } = await api.get(`/tickets/${ticket.id}/chat/history/`);
      if (data.conversation) {
        setConversationId(data.conversation.id);
        setMessages(data.conversation.messages);
      }
    } catch (error) {
      console.error('Error loading chat:', error);
    }
  };
  
  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    
    const messageText = inputText.trim();
    setInputText(''); // Clear input
    setIsLoading(true);
    
    try {
      const { data } = await api.post(`/tickets/${ticket.id}/chat/`, {
        message: messageText,
        conversation_id: conversationId
      });
      
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, data.user_message, data.ai_message]);
      
    } catch (error) {
      console.error('Error sending message:', error);
      alert('Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleFeedback = async (messageId, helpful) => {
    try {
      await api.post(`/tickets/${ticket.id}/chat/${messageId}/feedback/`, {
        was_helpful: helpful
      });
      setMessages(prev => prev.map(msg =>
        msg.id === messageId ? { ...msg, was_helpful: helpful } : msg
      ));
    } catch (error) {
      console.error('Error submitting feedback:', error);
    }
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b p-4">
        <h3 className="font-semibold">AI Assistant</h3>
        <p className="text-sm text-gray-500">
          Ask questions about ticket #{ticket.ticket_id}
        </p>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.sender_type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                msg.sender_type === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
              
              {/* Show confidence for AI messages */}
              {msg.sender_type === 'ai' && msg.confidence && (
                <div className="text-xs mt-2 opacity-75">
                  Confidence: {(msg.confidence * 100).toFixed(0)}%
                </div>
              )}
              
              {/* Feedback buttons for AI messages */}
              {msg.sender_type === 'ai' && (
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleFeedback(msg.id, true)}
                    className={`p-1 rounded ${msg.was_helpful === true ? 'bg-green-500 text-white' : 'hover:bg-gray-200'}`}
                  >
                    <ThumbsUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleFeedback(msg.id, false)}
                    className={`p-1 rounded ${msg.was_helpful === false ? 'bg-red-500 text-white' : 'hover:bg-gray-200'}`}
                  >
                    <ThumbsDown className="w-4 h-4" />
                  </button>
                </div>
              )}
              
              {/* Timestamp */}
              <div className="text-xs mt-1 opacity-75">
                {new Date(msg.created_at).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-3">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Input */}
      <form onSubmit={sendMessage} className="border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask the AI assistant..."
            className="flex-1 border rounded-lg px-4 py-2"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading}
            className="bg-blue-500 text-white px-6 py-2 rounded-lg disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
```

---

## 🔑 Key API Endpoints

### 1. Get Chat History
```http
GET /api/tickets/{ticket_id}/chat/history/

Response:
{
  "conversation": {
    "id": "uuid",
    "is_active": true,
    "resolved": false,
    "messages": [
      {
        "id": "uuid",
        "sender_type": "user",
        "text": "My printer won't connect",
        "created_at": "2026-03-04T10:30:00Z"
      },
      {
        "id": "uuid",
        "sender_type": "ai",
        "text": "Let's troubleshoot this...",
        "confidence": 0.85,
        "created_at": "2026-03-04T10:30:05Z"
      }
    ]
  }
}
```

### 2. Send Message
```http
POST /api/tickets/{ticket_id}/chat/
Body: {
  "message": "User's question or response",
  "conversation_id": "uuid" // Optional, created if not provided
}

Response:
{
  "conversation_id": "uuid",
  "user_message": { /* saved user message */ },
  "ai_message": { /* AI response with text, confidence, metadata */ }
}
```

### 3. Submit Feedback
```http
POST /api/tickets/{ticket_id}/chat/{message_id}/feedback/
Body: {
  "was_helpful": true,  // or false
  "feedback_comment": "This worked perfectly!" // optional
}
```

### 4. Get Quick Reply Suggestions
```http
GET /api/tickets/{ticket_id}/chat/suggestions/

Response:
{
  "suggestions": [
    {
      "id": "uuid",
      "label": "Show me similar tickets",
      "message_text": "Can you show me tickets similar to mine?"
    },
    {
      "label": "Connect me with a human",
      "message_text": "I'd like to speak with a support agent"
    }
  ]
}
```

---

## ✅ What User Can Do

1. **Ask Initial Question**
   - "My printer won't connect to WiFi"
   
2. **Get AI Response**
   - AI suggests troubleshooting steps
   
3. **Send Followup**
   - "I tried that, didn't work"
   
4. **Get Contextual Response**
   - AI knows what "that" refers to (previous steps)
   - Suggests alternative solutions
   
5. **Continue Conversation**
   - User can keep asking questions
   - AI maintains context throughout
   
6. **Provide Feedback**
   - Thumbs up/down on AI responses
   - Helps improve AI over time
   
7. **Apply Suggested Solutions**
   - AI can suggest specific actions
   - Frontend can trigger these via metadata
   
8. **Mark as Resolved**
   - When satisfied, conversation ends
   - Ticket status updated

---

## 🎭 Message Types Frontend Should Handle

The `message_type` field tells you how to render messages:

```javascript
// AI message types
switch (message.message_type) {
  case 'text':
    return <p>{message.text}</p>;
    
  case 'steps':
    return (
      <ol>
        {message.metadata.steps.map(step => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    );
    
  case 'solution':
    return (
      <div className="solution-card">
        <h4>Suggested Solution</h4>
        <p>{message.text}</p>
        <button onClick={applySolution}>Apply This Solution</button>
      </div>
    );
    
  case 'question':
    return (
      <div>
        <p>{message.text}</p>
        <div className="choices">
          {message.metadata.choices.map(choice => (
            <button key={choice} onClick={() => sendMessage(choice)}>
              {choice}
            </button>
          ))}
        </div>
      </div>
    );
    
  case 'similar_tickets':
    return <SimilarTicketsList tickets={message.metadata.tickets} />;
    
  case 'kb_article':
    return <KBArticleCard article={message.metadata.article} />;
}
```

---

## 🚫 Common Frontend Mistakes to Avoid

### ❌ Don't Create New Conversation for Each Message
```javascript
// WRONG:
await api.post(`/tickets/${ticketId}/chat/`, {
  message: text
  // Missing conversation_id - backend creates NEW conversation each time!
});
```

```javascript
// CORRECT:
await api.post(`/tickets/${ticketId}/chat/`, {
  message: text,
  conversation_id: conversationId // Reuse same conversation
});
```

### ❌ Don't Send Message Without Loading History First
```javascript
// WRONG: User opens ticket, starts typing immediately
// Problem: Frontend doesn't know about previous messages!

// CORRECT: Load history FIRST, then allow messaging
useEffect(() => {
  loadHistory();
}, [ticketId]);
```

### ❌ Don't Ignore metadata Field
```javascript
// WRONG: Only show message.text

// CORRECT: Check metadata for rich content
if (message.metadata?.quick_replies) {
  // Show quick reply buttons
}
if (message.metadata?.suggested_actions) {
  // Show action buttons
}
```

---

## 📚 Additional Documentation

For complete details, see:
- **[FRONTEND_AI_CHAT_GUIDE.md](./FRONTEND_AI_CHAT_GUIDE.md)** - Full React implementation
- **[AGENT_API.md](./AGENT_API.md#section-11)** - API reference
- **[typescript-chat-types.ts](./typescript-chat-types.ts)** - TypeScript types

---

## 🎯 Summary for Frontend Developer

**The system is already built! You just need to:**

1. ✅ Load conversation history when user opens ticket
2. ✅ Send user messages to `/chat/` endpoint
3. ✅ Display AI responses from the response
4. ✅ Include `conversation_id` in subsequent messages
5. ✅ Handle different message types (text, steps, solution, etc.)
6. ✅ Add thumbs up/down buttons for feedback
7. ✅ Render quick reply suggestions as buttons

**The backend handles:**
- Creating conversations automatically
- Maintaining context (last 10 messages)
- Calling AI agent with context
- Saving all messages
- Providing structured responses

**Think of it like a chat app** (WhatsApp, Slack):
- One chat per ticket
- Multiple messages back and forth
- All messages saved
- Context maintained throughout
