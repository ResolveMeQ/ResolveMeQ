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

from .models import Ticket, TicketResolution
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

    # First message in conversation = user is actively working on the ticket
    is_first_message = not ChatMessage.objects.filter(conversation=conversation).exists()
    if is_first_message and ticket.status in ("new", "open"):
        ticket.status = "in_progress"
        ticket.save(update_fields=["status"])

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
            'ai_message': ChatMessageSerializer(ai_message).data,
            'ticket_status': ticket.status,  # may have changed to in_progress on first message
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
            'ai_message': ChatMessageSerializer(fallback_message).data,
            'ticket_status': ticket.status,
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
    
    # Default suggestions when no QuickReply entries exist so users always have a way to start
    if not all_replies:
        default_suggestions = [
            {'label': 'Analyze this ticket', 'message_text': 'Please analyze this ticket', 'category': ticket.category or 'general'},
            {'label': 'Show possible solutions', 'message_text': 'Show me possible solutions', 'category': 'general'},
            {'label': 'Similar resolved tickets', 'message_text': 'Show similar resolved tickets', 'category': 'general'},
        ]
        return Response({
            'suggestions': default_suggestions,
            'ticket_id': ticket.ticket_id,
            'category': ticket.category
        })
    
    serializer = QuickReplySerializer(all_replies, many=True)
    return Response({
        'suggestions': serializer.data,
        'ticket_id': ticket.ticket_id,
        'category': ticket.category
    })


def _build_resolution_state(ticket, conversation):
    """Build resolution/feedback state so the agent can adapt actions and response."""
    state = {
        'ticket_status': getattr(ticket, 'status', 'open'),
        'conversation_resolved': getattr(conversation, 'resolved', False),
        'resolution_applied': getattr(conversation, 'resolution_applied', False),
    }
    resolution = TicketResolution.objects.filter(ticket=ticket).first()
    if resolution:
        state['resolution_confirmed'] = resolution.resolution_confirmed
        state['reopened'] = getattr(resolution, 'reopened', False)
        state['reopened_reason'] = getattr(resolution, 'reopened_reason', '') or ''
        state['user_feedback_text'] = (resolution.user_feedback_text or '').strip()
        state['satisfaction_score'] = resolution.satisfaction_score
    else:
        state['resolution_confirmed'] = None
        state['reopened'] = False
        state['reopened_reason'] = ''
        state['user_feedback_text'] = ''
        state['satisfaction_score'] = None
    # Last AI message feedback (so model knows if previous reply was unhelpful)
    last_ai = (
        conversation.messages.filter(sender_type='ai')
        .order_by('-created_at')
        .first()
    )
    if last_ai:
        state['last_ai_was_helpful'] = last_ai.was_helpful
        state['last_ai_feedback_comment'] = (last_ai.feedback_comment or '').strip()
    else:
        state['last_ai_was_helpful'] = None
        state['last_ai_feedback_comment'] = ''
    return state


def _get_ai_chat_response(ticket, message, conversation, user):
    """
    Internal function to get AI response for a chat message.
    Sends full conversation history and resolution state so the agent responds
    to the user's latest message in context and suggests contextual actions.
    """
    # Full conversation history for continuity (last 15 messages; model responds to latest)
    previous_messages = conversation.messages.order_by('created_at')[:15]
    conversation_history = []
    for msg in previous_messages:
        role = 'user' if msg.sender_type == 'user' else 'assistant'
        conversation_history.append({'role': role, 'text': msg.text or ''})
    # Current message is the one the model must respond to
    conversation_history.append({'role': 'user', 'text': message})

    resolution_state = _build_resolution_state(ticket, conversation)
    agent_data = ticket.agent_response if ticket.agent_processed else None

    payload = {
        'ticket_id': ticket.ticket_id,
        'issue_type': ticket.issue_type,
        'description': ticket.description or '',
        'category': ticket.category,
        'tags': ticket.tags or [],
        'user': {
            'id': str(user.id),
            'name': user.username,
            'department': getattr(user, 'department', ''),
        },
        'conversation_history': conversation_history,
        'resolution_state': resolution_state,
    }
    
    # Try to get response from AI agent
    agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.net/tickets/analyze/')
    
    try:
        response = requests.post(
            agent_url,  # Use the standard /analyze/ endpoint
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=25  # Chat may include RAG + long context; allow a bit more time
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
        
        # Determine message type and metadata so frontend can show steps, time, success rate
        message_type = 'text'
        steps_list = []
        estimated_time = None
        success_probability = None
        if isinstance(solution, dict):
            if solution.get('steps'):
                message_type = 'steps' if len(solution['steps']) > 1 else 'text'
                steps_list = solution['steps']
            estimated_time = solution.get('estimated_time')
            success_probability = solution.get('success_probability')

        metadata = {
            'full_solution': solution if isinstance(solution, dict) else None,
            'analysis': data.get('analysis', {}),
            'suggested_actions': _extract_actions_from_response(data, ticket, resolution_state),
            'quick_replies': _generate_quick_replies(data, ticket, resolution_state),
        }
        if steps_list:
            metadata['steps'] = steps_list
        if estimated_time:
            metadata['estimated_time'] = estimated_time
        if success_probability is not None:
            metadata['success_probability'] = success_probability

        return {
            'text': chat_text,
            'confidence': data.get('confidence', 0.5),
            'message_type': message_type,
            'metadata': metadata,
        }
            
    except Exception as e:
        logger.error(f"Error calling AI agent for chat: {e}")
        
        # Fallback to simple response based on ticket data
        return _generate_fallback_response(message, ticket, agent_data)


def _extract_actions_from_response(data, ticket, resolution_state=None):
    """Extract suggested actions from agent response. Only include real actions (resolve, escalate, clarify).
    Do NOT include immediate_actions - those are step-like instructions already shown in the main content.
    Showing them as clickable buttons causes confusion; steps are read, not clicked."""
    actions = []
    state = resolution_state or {}
    ticket_status = getattr(ticket, 'status', '') or state.get('ticket_status', '')
    reopened = state.get('reopened', False)
    resolution_confirmed = state.get('resolution_confirmed')

    if 'recommended_action' in data:
        ra = data['recommended_action'].replace('_', ' ').title()
        # Don't suggest Auto Resolve if ticket was reopened or user said it didn't work
        if reopened or resolution_confirmed is False:
            if 'auto' in ra.lower() or 'resolve' in ra.lower():
                ra = 'Escalate'  # Prefer escalation after failed resolution
        # Friendlier label for users going step-by-step: "Mark as resolved" encourages good closure
        if ra.lower() == 'auto resolve':
            ra = 'Mark as resolved'
        actions.append(ra)

    # Do NOT add immediate_actions - they are instructional steps, not clickable actions.
    # They duplicate the steps already shown and confuse users when rendered as buttons.

    # If already resolved, drop "Apply this solution" style actions
    if ticket_status == 'resolved':
        actions = [a for a in actions if 'apply' not in a.lower() and 'resolve' not in a.lower()]
    return actions[:5]


def _generate_quick_replies(data, ticket, resolution_state=None):
    """Generate quick replies based on resolution outcome and ticket status."""
    replies = []
    state = resolution_state or {}
    ticket_status = getattr(ticket, 'status', '') or state.get('ticket_status', '')
    reopened = state.get('reopened', False)
    resolution_confirmed = state.get('resolution_confirmed')
    last_ai_was_helpful = state.get('last_ai_was_helpful')

    if data.get('recommended_action') == 'request_clarification':
        replies.append({
            'label': 'Provide more details',
            'value': 'I can provide more information about the issue'
        })

    # Only suggest "Apply this solution" if not already resolved and not reopened
    if ticket_status != 'resolved' and not reopened and resolution_confirmed is not False:
        if data.get('confidence', 0) >= 0.8:
            replies.append({
                'label': 'Apply this solution',
                'value': 'Please apply this solution to my ticket'
            })

    # After failed resolution or reopen, offer alternatives
    if reopened or resolution_confirmed is False:
        replies.append({
            'label': 'Try a different approach',
            'value': 'The previous solution did not work, I need a different approach'
        })
        replies.append({
            'label': 'Escalate to human',
            'value': 'I need to speak with support staff'
        })
    if last_ai_was_helpful is False and not any(r.get('value', '').find('different') >= 0 for r in replies):
        replies.append({
            'label': 'That didn\'t help',
            'value': 'That didn\'t help me, I need different guidance'
        })

    # Step-by-step follow-up: when we have solution steps and ticket not resolved, help user until they mark resolved
    if ticket_status != 'resolved' and not reopened:
        solution = data.get('solution') or {}
        steps = solution.get('steps') or []
        if len(steps) > 1:
            if not any(r.get('value', '').find('first step') >= 0 for r in replies):
                replies.append({'label': 'I did the first step', 'value': 'I tried the first step. What should I do next?'})
            if not any(r.get('value', '').find('next step') >= 0 for r in replies):
                replies.append({'label': 'Next step', 'value': 'I\'m ready for the next step'})
            if not any(r.get('value', '').find('fixed') >= 0 for r in replies):
                replies.append({'label': 'It\'s fixed', 'value': 'It\'s fixed now, thank you!'})
            if not any(r.get('value', '').find('Still not working') >= 0 for r in replies):
                replies.append({'label': 'Still not working', 'value': 'Still not working. What else can I try?'})
        elif len(steps) == 1:
            if not any(r.get('value', '').find('fixed') >= 0 for r in replies):
                replies.append({'label': 'It\'s fixed', 'value': 'It\'s fixed now, thank you!'})
            if not any(r.get('value', '').find('Still not working') >= 0 for r in replies):
                replies.append({'label': 'Still not working', 'value': 'Still not working. What else can I try?'})

    # Always offer these (avoid duplicates)
    for label, value in [
        ('Show similar tickets', 'Show me similar resolved tickets'),
        ('Talk to a human', 'I need to speak with support staff'),
    ]:
        if not any(r.get('value') == value for r in replies):
            replies.append({'label': label, 'value': value})

    return replies[:8]


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
