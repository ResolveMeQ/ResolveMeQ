"""
Chat conversation views for AI assistant.
Provides real-time, contextual AI chat functionality.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.conf import settings
import requests
import logging

from .models import Ticket
from .chat_models import Conversation, ChatMessage, QuickReply
from .chat_serializers import (
    ConversationSerializer, ChatMessageSerializer, QuickReplySerializer
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_or_get_conversation(request, ticket_id):
    """
    Start a new conversation or get existing active conversation for a ticket.
    
    GET: Returns active conversation if exists
    POST: Creates new conversation or returns existing
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Check permissions
    if ticket.user != request.user and not request.user.is_staff:
        return Response(
            {"error": "You don't have permission to access this ticket"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get or create active conversation
    conversation, created = Conversation.objects.get_or_create(
        ticket=ticket,
        user=request.user,
        is_active=True,
        defaults={'summary': f'Chat about: {ticket.issue_type}'}
    )
    
    serializer = ConversationSerializer(conversation)
    return Response({
        'conversation': serializer.data,
        'created': created
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_chat_message(request, ticket_id):
    """
    Send a message in the chat conversation and get AI response.
    
    POST /api/tickets/{ticket_id}/chat/
    Body: {
        "message": "User's message text",
        "conversation_id": "uuid" (optional, will create if not provided)
    }
    
    Returns: {
        "conversation_id": "uuid",
        "user_message": {...},
        "ai_message": {
            "id": "uuid",
            "text": "AI response",
            "confidence": 0.85,
            "message_type": "text|steps|solution",
            "metadata": {
                "suggested_actions": ["action1", "action2"],
                "quick_replies": [{label: "...", value: "..."}],
                "attachments": [...]
            }
        }
    }
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Permission check
    if ticket.user != request.user and not request.user.is_staff:
        return Response(
            {"error": "You don't have permission to access this ticket"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    message_text = request.data.get('message', '').strip()
    if not message_text:
        return Response(
            {"error": "Message text is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    conversation_id = request.data.get('conversation_id')
    
    # Get or create conversation
    if conversation_id:
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            ticket=ticket,
            user=request.user
        )
    else:
        conversation, _ = Conversation.objects.get_or_create(
            ticket=ticket,
            user=request.user,
            is_active=True,
            defaults={'summary': f'Chat about: {ticket.issue_type}'}
        )
    
    # Save user message
    user_message = ChatMessage.objects.create(
        conversation=conversation,
        sender_type='user',
        message_type='text',
        text=message_text
    )
    
    # Get AI response
    try:
        ai_response = _get_ai_chat_response(
            ticket=ticket,
            message=message_text,
            conversation=conversation,
            user=request.user
        )
        
        # Save AI message
        ai_message = ChatMessage.objects.create(
            conversation=conversation,
            sender_type='ai',
            message_type=ai_response.get('message_type', 'text'),
            text=ai_response.get('text', ''),
            confidence=ai_response.get('confidence'),
            metadata=ai_response.get('metadata', {}),
            agent_response_data=ai_response
        )
        
        return Response({
            'conversation_id': str(conversation.id),
            'user_message': ChatMessageSerializer(user_message).data,
            'ai_message': ChatMessageSerializer(ai_message).data
        })
        
    except Exception as e:
        logger.error(f"Error getting AI response: {e}")
        
        # Create fallback message
        fallback_message = ChatMessage.objects.create(
            conversation=conversation,
            sender_type='system',
            message_type='text',
            text="I'm having trouble processing your request right now. Please try again or contact support."
        )
        
        return Response({
            'conversation_id': str(conversation.id),
            'user_message': ChatMessageSerializer(user_message).data,
            'ai_message': ChatMessageSerializer(fallback_message).data
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_history(request, ticket_id):
    """
    Get chat conversation history for a ticket.
    
    Returns all messages in the active conversation.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if ticket.user != request.user and not request.user.is_staff:
        return Response(
            {"error": "You don't have permission to access this ticket"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get active conversation
    try:
        conversation = Conversation.objects.get(
            ticket=ticket,
            user=request.user,
            is_active=True
        )
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)
    except Conversation.DoesNotExist:
        return Response({
            'conversation': None,
            'messages': []
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_message_feedback(request, ticket_id, message_id):
    """
    Submit feedback on an AI message.
    
    POST /api/tickets/{ticket_id}/chat/{message_id}/feedback/
    Body: {
        "rating": "helpful" | "not_helpful",
        "comment": "Optional feedback comment"
    }
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    message = get_object_or_404(ChatMessage, id=message_id)
    
    # Permission check
    if message.conversation.user != request.user:
        return Response(
            {"error": "You don't have permission to rate this message"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    rating = request.data.get('rating')
    if rating not in ['helpful', 'not_helpful']:
        return Response(
            {"error": "Rating must be 'helpful' or 'not_helpful'"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    message.was_helpful = (rating == 'helpful')
    message.feedback_comment = request.data.get('comment', '')
    from django.utils import timezone
    message.feedback_at = timezone.now()
    message.save()
    
    return Response({
        'message': 'Feedback submitted successfully',
        'message_id': str(message.id),
        'was_helpful': message.was_helpful
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_suggested_questions(request, ticket_id):
    """
    Get suggested questions/quick replies for the ticket.
    
    Returns context-aware suggestions based on ticket category and status.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Get quick replies for this category
    quick_replies = QuickReply.objects.filter(
        category=ticket.category,
        is_active=True
    )[:5]
    
    # Add general suggestions
    general_replies = QuickReply.objects.filter(
        category='general',
        is_active=True
    )[:3]
    
    all_replies = list(quick_replies) + list(general_replies)
    
    serializer = QuickReplySerializer(all_replies, many=True)
    
    return Response({
        'suggestions': serializer.data,
        'ticket_id': ticket.ticket_id,
        'category': ticket.category
    })


def _get_ai_chat_response(ticket, message, conversation, user):
    """
    Internal function to get AI response for a chat message.
    
    This integrates with the existing AI agent or can use a chat-specific endpoint.
    """
    # Build context from conversation history
    previous_messages = conversation.messages.order_by('created_at')[:10]
    context = [
        {
            'sender': msg.sender_type,
            'text': msg.text,
            'type': msg.message_type
        }
        for msg in previous_messages
    ]
    
    # Check if ticket has agent response already
    agent_data = ticket.agent_response if ticket.agent_processed else None
    
    # Prepare payload for AI agent (use standard /analyze/ endpoint format)
    # Include chat context in the description for context-aware responses
    description_with_context = ticket.description
    if context:
        # Add conversation context to description
        context_summary = "\n\n--- Conversation Context ---\n"
        for msg in context[-3:]:  # Last 3 messages for context
            context_summary += f"{msg['sender']}: {msg['text']}\n"
        context_summary += f"User's current message: {message}"
        description_with_context = ticket.description + context_summary
    else:
        description_with_context = f"{ticket.description}\n\nUser message: {message}"
    
    payload = {
        'ticket_id': ticket.ticket_id,
        'issue_type': ticket.issue_type,
        'description': description_with_context,
        'category': ticket.category,
        'tags': ticket.tags or [],
        'user': {
            'id': str(user.id),
            'name': user.username,
            'department': getattr(user, 'department', ''),
        }
    }
    
    # Try to get response from AI agent
    agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.net/tickets/analyze/')
    
    try:
        response = requests.post(
            agent_url,  # Use the standard /analyze/ endpoint
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        # Format response for chat - convert full analysis to conversational response
        solution = data.get('solution', {})
        
        # Extract the solution text
        if isinstance(solution, dict):
            steps = solution.get('steps', [])
            if isinstance(steps, list) and steps:
                # Create conversational response from steps
                if len(steps) == 1:
                    chat_text = steps[0]
                elif len(steps) <= 3:
                    chat_text = "Here's what I suggest:\n\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))
                else:
                    # Show first 3 steps, offer to show more
                    chat_text = "Here are the first steps to try:\n\n"
                    chat_text += "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps[:3]))
                    chat_text += f"\n\nThere are {len(steps) - 3} more steps. Would you like to see them?"
            else:
                chat_text = solution.get('description', "I've analyzed your issue. Let me help you resolve it.")
        elif isinstance(solution, str):
            chat_text = solution
        else:
            chat_text = "I've analyzed your issue and I'm here to help. Can you provide more details?"
        
        # Determine message type
        message_type = 'text'
        if isinstance(solution, dict) and solution.get('steps'):
            message_type = 'steps' if len(solution['steps']) > 1 else 'text'
        
        return {
            'text': chat_text,
            'confidence': data.get('confidence', 0.5),
            'message_type': message_type,
            'metadata': {
                'full_solution': solution if isinstance(solution, dict) else None,
                'analysis': data.get('analysis', {}),
                'suggested_actions': _extract_actions_from_response(data),
                'quick_replies': _generate_quick_replies(data, ticket),
            }
        }
            
    except Exception as e:
        logger.error(f"Error calling AI agent for chat: {e}")
        
        # Fallback to simple response based on ticket data
        return _generate_fallback_response(message, ticket, agent_data)


def _extract_actions_from_response(data):
    """Extract suggested actions from agent response."""
    actions = []
    
    if 'recommended_action' in data:
        actions.append(data['recommended_action'].replace('_', ' ').title())
    
    if 'solution' in data and isinstance(data['solution'], dict):
        immediate = data['solution'].get('immediate_actions', [])
        if immediate:
            actions.extend(immediate[:3])
    
    return actions[:5]


def _generate_quick_replies(data, ticket):
    """Generate contextual quick replies."""
    replies = []
    
    # Based on recommended action
    if data.get('recommended_action') == 'request_clarification':
        replies.append({
            'label': 'Provide more details',
            'value': 'I can provide more information about the issue'
        })
    
    if data.get('confidence', 0) >= 0.8:
        replies.append({
            'label': 'Apply this solution',
            'value': 'Please apply this solution to my ticket'
        })
    
    # Always offer these
    replies.extend([
        {'label': 'Show similar tickets', 'value': 'Show me similar resolved tickets'},
        {'label': 'Talk to a human', 'value': 'I need to speak with support staff'},
    ])
    
    return replies[:4]


def _generate_fallback_response(message, ticket, agent_data):
    """Generate a helpful fallback response when AI is unavailable."""
    text = "I understand you're asking about "
    
    if ticket.category:
        text += f"{ticket.category} issues. "
    
    if agent_data and isinstance(agent_data, dict):
        confidence = agent_data.get('confidence', 0)
        if confidence >= 0.7:
            text += "Based on our AI analysis, we've identified some potential solutions. Would you like me to share them?"
        else:
            text += "This seems like a complex issue. I recommend getting help from our support team."
    else:
        text += "Let me analyze your ticket to provide better assistance."
    
    return {
        'text': text,
        'confidence': 0.5,
        'message_type': 'text',
        'metadata': {
            'quick_replies': [
                {'label': 'Yes, show solutions', 'value': 'Show me the solutions'},
                {'label': 'No, escalate to human', 'value': 'Connect me with support'},
            ]
        }
    }
