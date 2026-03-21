from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField, Q
from django.db.models.functions import TruncWeek
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import UserRateThrottle, ScopedRateThrottle
from celery.result import AsyncResult
from celery.exceptions import OperationalError
from .models import Ticket, TicketInteraction, ActionHistory, TicketResolution
from .tasks import process_ticket_with_agent
from .serializers import TicketSerializer, TicketInteractionSerializer
from .cache_decorators import cache_api_response, no_cache
import logging
import os
from django.conf import settings
from base.models import User, InAppNotification
from base.permissions import IsAuthenticatedOrAgent
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def _tickets_for_user(request):
    """Return ticket queryset for listing/analytics: tickets CREATED BY the current user. Staff see all."""
    if not getattr(request.user, 'is_authenticated', False):
        return Ticket.objects.none()
    if request.user.is_staff:
        return Ticket.objects.all()
    return Ticket.objects.filter(user=request.user)


def _can_access_ticket(request, ticket):
    """Return True if the user can access this ticket (staff, creator, or assignee)."""
    if not getattr(request.user, 'is_authenticated', False):
        return False
    if request.user.is_staff:
        return True
    return (
        ticket.user_id == request.user.id
        or (ticket.assigned_to_id and ticket.assigned_to_id == request.user.id)
    )


class AgentActionThrottle(UserRateThrottle):
    """Custom throttle for agent actions"""
    scope = 'agent_actions'


class RollbackThrottle(UserRateThrottle):
    """Custom throttle for rollback actions"""
    scope = 'rollback'

# Create your views here.

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ticket_analytics(request):
    """
    Get ticket analytics data: tickets per week, average resolution time, open/closed ticket count.
    """
    base_qs = Ticket.objects.all()
    now = timezone.now()
    weeks_ago = now - timezone.timedelta(weeks=8)
    tickets_per_week = (
        base_qs.filter(created_at__gte=weeks_ago)
        .annotate(week=TruncWeek("created_at"))
        .values("week")
        .annotate(count=Count("ticket_id"))
        .order_by("week")
    )

    # Avg resolution time (tickets with status 'resolved')
    resolved_tickets = base_qs.filter(status="resolved", updated_at__gt=F("created_at"))
    avg_resolution = resolved_tickets.annotate(
        resolution_time=ExpressionWrapper(F("updated_at") - F("created_at"), output_field=DurationField())
    ).aggregate(avg_time=Avg("resolution_time"))["avg_time"]

    # Open vs closed tickets
    open_count = base_qs.exclude(status="resolved").count()
    closed_count = base_qs.filter(status="resolved").count()

    return Response({
        "tickets_per_week": list(tickets_per_week),
        "avg_resolution_time_seconds": avg_resolution.total_seconds() if avg_resolution else None,
        "open_tickets": open_count,
        "closed_tickets": closed_count,
    })

@api_view(['POST'])
@throttle_classes([AgentActionThrottle])
def process_with_agent(request, ticket_id):
    """
    Manually trigger AI agent processing for a ticket.
    Uses Celery task for background processing, with synchronous fallback.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Check if force re-processing is requested
    force = request.data.get('force', False) or request.data.get('reset', False)
    
    # Reset agent processing status if requested
    if request.data.get('reset', False):
        ticket.agent_processed = False
        ticket.agent_response = None
        ticket.save()
    
    # Check if we should force synchronous processing (for local dev without Celery workers)
    force_sync = os.getenv('FORCE_SYNC_AGENT_PROCESSING', 'false').lower() == 'true'
    
    # Queue the task
    try:
        if force_sync:
            raise OperationalError("Forced synchronous processing enabled")
        
        task = process_ticket_with_agent.delay(ticket.ticket_id, force=force)
        logger.info(f"Queued Celery task: {task.id} for ticket {ticket.ticket_id} (force={force})")
        task_id = task.id
        status_msg = 'queued'
    except OperationalError as e:
        logger.warning(f"Celery unavailable, processing synchronously: {e}")
        
        # Fallback: Process synchronously
        try:
            import requests
            from tickets.autonomous_agent import AutonomousAgent
            
            # Build payload
            payload = {
                "ticket_id": ticket.ticket_id,
                "issue_type": ticket.issue_type or "",
                "description": ticket.description or "",
                "category": ticket.category or "",
                "tags": ticket.tags or [],
                "user": {
                    "id": str(ticket.user.id),
                    "name": ticket.user.username,
                    "department": getattr(ticket.user, "department", "")
                }
            }
            
            # Try to send to agent
            agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.net/tickets/analyze/')
            headers_req = {"Content-Type": "application/json"}
            
            try:
                logger.info(f"Sending POST to AI agent (sync): {agent_url}")
                response = requests.post(agent_url, json=payload, headers=headers_req, timeout=10)
                response.raise_for_status()
                agent_response = response.json()
            except Exception as agent_error:
                # If agent is unavailable, create a mock response
                logger.warning(f"AI Agent unavailable, using mock response: {agent_error}")
                agent_response = {
                    "confidence": 0.75,
                    "recommended_action": "request_clarification",
                    "analysis": {
                        "category": ticket.category or "general",
                        "severity": "medium",
                        "complexity": "medium",
                        "suggested_team": "IT Support"
                    },
                    "solution": {
                        "steps": [
                            "This is a mock response - AI agent is currently unavailable",
                            "Please check the issue description and category",
                            "You can manually assign this ticket to the appropriate team"
                        ],
                        "estimated_time": "Pending agent availability",
                        "success_probability": 0.5
                    },
                    "reasoning": "AI agent service is currently unavailable. This is a placeholder response."
                }
            
            # Update ticket with agent response
            ticket.agent_response = agent_response
            ticket.agent_processed = True
            ticket.save()
            
            logger.info(f"Ticket {ticket.ticket_id} processed synchronously")
            task_id = None
            status_msg = 'completed'
            
        except Exception as sync_error:
            logger.error(f"Synchronous processing failed: {sync_error}")
            task_id = None
            status_msg = 'error'
            return Response({
                'task_id': task_id,
                'ticket_id': ticket.ticket_id,
                'status': status_msg,
                'error': str(sync_error),
                'agent_processed': ticket.agent_processed
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'task_id': task_id,
        'ticket_id': ticket.ticket_id,
        'status': status_msg,
        'agent_processed': ticket.agent_processed
    })

@api_view(['GET'])
def task_status(request, task_id):
    """
    Check the status of a Celery task.
    """
    task_result = AsyncResult(task_id)
    response = {
        'task_id': task_id,
        'status': task_result.status,
        'successful': task_result.successful(),
        'failed': task_result.failed(),
    }
    
    if task_result.ready():
        if task_result.successful():
            response['result'] = task_result.result
        else:
            response['error'] = str(task_result.result)
    
    return Response(response)

@api_view(['GET'])
def ticket_agent_status(request, ticket_id):
    """
    Get the agent processing status and history for a ticket.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Get the latest task for this ticket from Celery
    ticket_tasks = []
    
    try:
        from celery import current_app
        i = current_app.control.inspect()
        active_tasks = i.active() or {}
        scheduled_tasks = i.scheduled() or {}
        
        # Find tasks related to this ticket
        for worker_tasks in active_tasks.values():
            for task in worker_tasks:
                # Safely check if task has required keys
                task_name = task.get('name')
                task_args = task.get('args', [])
                if task_name == 'tickets.tasks.process_ticket_with_agent' and str(ticket_id) in str(task_args):
                    ticket_tasks.append({
                        'task_id': task.get('id'),
                        'status': 'active',
                        'started_at': task.get('time_start'),
                    })
        
        for worker_tasks in scheduled_tasks.values():
            for task in worker_tasks:
                # Safely check if task has required keys
                task_name = task.get('name')
                task_args = task.get('args', [])
                if task_name == 'tickets.tasks.process_ticket_with_agent' and str(ticket_id) in str(task_args):
                    ticket_tasks.append({
                        'task_id': task.get('id'),
                        'status': 'scheduled',
                        'eta': task.get('eta'),
                    })
    except Exception as e:
        # If Celery is not available or inspect fails, just return empty task list
        logger.warning(f"Could not inspect Celery tasks: {str(e)}")
    
    return Response({
        'ticket_id': ticket.ticket_id,
        'agent_processed': ticket.agent_processed,
        'agent_response': ticket.agent_response,
        'active_tasks': ticket_tasks,
        'last_updated': ticket.updated_at,
    })

@api_view(["POST"])
def create_ticket(request):
    """
    Create a new ticket. If authenticated, use request.user; else body must include user (UUID).
    """
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    if getattr(request, 'user', None) and request.user.is_authenticated:
        data['user'] = str(request.user.pk)
    serializer = TicketSerializer(data=data)
    if serializer.is_valid():
        user_id = data.get("user")
        if not user_id:
            return Response({"user": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"user": ["User not found."]}, status=status.HTTP_400_BAD_REQUEST)
        ticket = serializer.save(user=user, status=data.get("status", "new"))
        # Usage/billing: attribute to request.user.preferences.active_team when needed
        TicketInteraction.objects.create(
            ticket=ticket,
            user=user,
            interaction_type="user_message",
            content=f"Ticket created: {ticket.description}"
        )
        try:
            InAppNotification.objects.create(
                user=user,
                type=InAppNotification.Type.INFO,
                title="Ticket created",
                message=f"Ticket #{ticket.ticket_id} has been created. We'll get back to you soon.",
                link=f"/tickets?highlight={ticket.ticket_id}",
            )
        except Exception as e:
            logger.warning("Failed to create ticket-created notification: %s", e)
        # Optionally trigger agent processing
        from .tasks import process_ticket_with_agent
        process_ticket_with_agent.delay(ticket.ticket_id)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def clarify_ticket(request, ticket_id):
    """
    Add clarification to a ticket (web portal).
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    description = request.data.get("description")
    issue_type = request.data.get("issue_type")
    if not description or not issue_type:
        return Response({"error": "Description and issue_type are required."}, status=400)
    ticket.description = description
    ticket.issue_type = issue_type
    ticket.save()
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="clarification",
        content=f"User clarified: Description='{description}', Issue Type='{issue_type}'"
    )
    from .tasks import process_ticket_with_agent
    process_ticket_with_agent.delay(ticket.ticket_id)
    return Response(TicketSerializer(ticket).data)

@api_view(["POST"])
def feedback_ticket(request, ticket_id):
    """
    Add feedback to a ticket (web portal).
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    feedback = request.data.get("feedback")
    if not feedback:
        return Response({"error": "Feedback is required."}, status=400)
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="feedback",
        content=f"User feedback: {feedback}"
    )
    return Response({"message": "Feedback received."})

@api_view(["GET"])
def ticket_history(request, ticket_id):
    """
    Get ticket history (recent interactions).
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    interactions = TicketInteraction.objects.filter(ticket=ticket).order_by("-created_at")[:10]
    serializer = TicketInteractionSerializer(interactions, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_tickets(request):
    """
    List tickets for the current user (staff see all). Query params: status, limit, offset.
    """
    status_param = request.GET.get("status")
    limit = request.GET.get("limit")
    offset = request.GET.get("offset", "0")
    try:
        limit = int(limit) if limit else None
    except ValueError:
        limit = None
    try:
        offset = int(offset)
    except ValueError:
        offset = 0
    queryset = _tickets_for_user(request).order_by("-created_at")
    if status_param:
        queryset = queryset.filter(status=status_param)
    if offset:
        queryset = queryset[offset:]
    if limit is not None:
        queryset = queryset[:limit]
    serializer = TicketSerializer(queryset, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_ticket(request, ticket_id):
    """
    Retrieve details for a single ticket by ticket_id.
    Includes comments (user_message interactions) for the ticket panel.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    serializer = TicketSerializer(ticket)
    data = dict(serializer.data)
    # Include comments so the ticket panel can display them
    interactions = TicketInteraction.objects.filter(
        ticket=ticket,
        interaction_type="user_message"
    ).order_by("created_at").select_related("user")
    comments = []
    for i in interactions:
        text = i.content
        if text.startswith("Comment: "):
            text = text[9:].strip()
        author = (getattr(i.user, "get_full_name", lambda: "")() or getattr(i.user, "username", "") or "User").strip() or "User"
        comments.append({
            "id": i.id,
            "content": text,
            "author": author,
            "created_at": i.created_at,
        })
    data["comments"] = comments
    # Include whether resolution feedback was already submitted (prevent double-submit)
    try:
        resolution = TicketResolution.objects.get(ticket=ticket)
        data["resolution_feedback_submitted"] = resolution.response_received_at is not None
    except TicketResolution.DoesNotExist:
        data["resolution_feedback_submitted"] = False
    return Response(data)

@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_ticket(request, ticket_id):
    """
    Update ticket status or details. Accepts partial updates.
    Example body: {"status": "resolved"}
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    serializer = TicketSerializer(ticket, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_ticket(request, ticket_id):
    """
    Delete a ticket.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    ticket.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_tickets(request):
    """
    Search and filter tickets (scoped to current user; staff see all).
    Query params: q (keyword), status, category, created_after, created_before
    """
    queryset = _tickets_for_user(request)
    q = request.GET.get("q")
    if q:
        queryset = queryset.filter(description__icontains=q)
    status_param = request.GET.get("status")
    if status_param:
        queryset = queryset.filter(status=status_param)
    category = request.GET.get("category")
    if category:
        queryset = queryset.filter(category=category)
    created_after = request.GET.get("created_after")
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    created_before = request.GET.get("created_before")
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)
    serializer = TicketSerializer(queryset.order_by("-created_at"), many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_attachment(request, ticket_id):
    """
    Upload an attachment (file) to a ticket. Use multipart/form-data.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "No file uploaded."}, status=400)
    filename = default_storage.save(f"ticket_{ticket_id}/{file.name}", file)
    # Optionally, store file URL in ticket or as a TicketInteraction
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="user_message",
        content=f"Attachment uploaded: {filename}"
    )
    return Response({"message": "File uploaded.", "file_url": default_storage.url(filename)})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_comment(request, ticket_id):
    """
    Add a comment to a ticket (threaded discussion).
    Body: {"comment": "..."}
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    if ticket.user != request.user and not request.user.is_staff:
        return Response(
            {"error": "You don't have permission to comment on this ticket."},
            status=status.HTTP_403_FORBIDDEN
        )
    comment = request.data.get("comment")
    if not comment:
        return Response({"error": "Comment is required."}, status=400)
    TicketInteraction.objects.create(
        ticket=ticket,
        user=request.user,
        interaction_type="user_message",
        content=f"Comment: {comment}"
    )
    return Response({"message": "Comment added."})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def escalate_ticket(request, ticket_id):
    """
    Escalate a ticket for priority handling.
    Body (optional): {"conversation_summary": "..."} - brief context for human agents.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    if ticket.user != request.user and not request.user.is_staff:
        return Response(
            {"error": "You don't have permission to escalate this ticket."},
            status=status.HTTP_403_FORBIDDEN
        )
    ticket.status = "escalated"
    ticket.save()

    content = "Ticket escalated by user."
    conversation_summary = (request.data.get("conversation_summary") or "").strip()
    if conversation_summary:
        content += f"\n\nConversation context for support:\n{conversation_summary[:2000]}"

    TicketInteraction.objects.create(
        ticket=ticket,
        user=request.user,
        interaction_type="user_message",
        content=content
    )
    _notify_ticket_status_change(ticket, "escalated")
    params = {"reason": "Escalated by user"}
    if conversation_summary:
        params["conversation_summary"] = conversation_summary[:500]
    try:
        from integrations.views import notify_escalation
        notify_escalation(str(ticket.user.id), ticket.ticket_id, params)
    except Exception:
        pass
    from .notifications import notify_support_escalation
    notify_support_escalation(ticket, params)
    return Response({
        "message": "Ticket escalated.",
        "ticket": TicketSerializer(ticket).data,
    })

@api_view(["POST"])
def assign_ticket(request, ticket_id):
    """
    Assign or reassign a ticket to an agent.
    Body: {"agent_id": "..."}
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    agent_id = request.data.get("agent_id")
    if not agent_id:
        return Response({"error": "agent_id is required."}, status=400)
    from base.models import User
    agent = get_object_or_404(User, user_id=agent_id)
    ticket.assigned_to = agent
    ticket.save()
    TicketInteraction.objects.create(
        ticket=ticket,
        user=agent,
        interaction_type="user_message",
        content="Ticket assigned to agent."
    )
    return Response({"message": f"Ticket assigned to {agent.name}."})

def _notify_ticket_status_change(ticket, new_status):
    """Create in-app notification for ticket owner and trigger Slack if applicable."""
    try:
        if new_status == "resolved":
            InAppNotification.objects.create(
                user=ticket.user,
                type=InAppNotification.Type.SUCCESS,
                title="Ticket resolved",
                message=f"Ticket #{ticket.ticket_id} has been marked as resolved.",
                link=f"/tickets?highlight={ticket.ticket_id}",
            )
            try:
                from integrations.views import notify_user_ticket_resolved
                # Slack expects channel ID; if user has linked Slack it may be stored elsewhere
                notify_user_ticket_resolved(str(ticket.user.id), ticket.ticket_id)
            except Exception:
                pass
        elif new_status == "escalated":
            InAppNotification.objects.create(
                user=ticket.user,
                type=InAppNotification.Type.WARNING,
                title="Ticket escalated",
                message=f"Ticket #{ticket.ticket_id} has been escalated to support.",
                link=f"/tickets?highlight={ticket.ticket_id}",
            )
    except Exception as e:
        logger.warning("Failed to create status-change notification: %s", e)


# Allowed ticket statuses; normalize aliases to canonical form for storage
ALLOWED_TICKET_STATUSES = frozenset([
    "new", "open", "in_progress", "in-progress", "pending_clarification",
    "escalated", "resolved"
])
CANONICAL_STATUS = {
    "in-progress": "in_progress",  # normalize hyphen to underscore
}


def _normalize_ticket_status(status_val):
    """Validate and normalize status; returns (canonical_status, error_msg)."""
    if not status_val or not isinstance(status_val, str):
        return None, "status is required."
    raw = status_val.strip().lower()
    if raw not in ALLOWED_TICKET_STATUSES:
        return None, f"status must be one of: new, open, in_progress, pending_clarification, escalated, resolved"
    return CANONICAL_STATUS.get(raw, raw), None


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAgent])
def update_ticket_status(request, ticket_id):
    """
    Update ticket status (close, cancel, reopen, etc.).
    Body: {"status": "resolved"}
    Allows both authenticated users and AI Agent with API key.
    Returns updated ticket for immediate UI updates.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    status_val = request.data.get("status")
    canonical, err = _normalize_ticket_status(status_val)
    if err:
        return Response({"error": err}, status=400)
    previous_status = getattr(ticket, "status", None)
    ticket.status = canonical
    ticket.save()

    # Determine who made the change
    user = request.user if request.user and request.user.is_authenticated else ticket.user

    TicketInteraction.objects.create(
        ticket=ticket,
        user=user,
        interaction_type="agent_response" if request.auth and not request.user else "user_message",
        content=f"Status updated to {canonical}.",
    )
    if previous_status != canonical:
        _notify_ticket_status_change(ticket, canonical)
    return Response({
        "message": f"Ticket status updated to {canonical}.",
        "ticket": TicketSerializer(ticket).data,
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def escalation_queue(request):
    """
    List escalated tickets for support staff.
    Staff only (is_staff=True). Returns tickets needing human attention.
    Query params: limit (default 50), offset (default 0).
    """
    if not getattr(request.user, "is_staff", False):
        return Response({"error": "Staff access required."}, status=status.HTTP_403_FORBIDDEN)
    limit = min(int(request.GET.get("limit", 50)), 100)
    offset = int(request.GET.get("offset", 0))
    queryset = (
        Ticket.objects.filter(status="escalated")
        .select_related("user")
        .order_by("-created_at")
    )
    total = queryset.count()
    queryset = queryset[offset : offset + limit]
    serializer = TicketSerializer(queryset, many=True)
    return Response({
        "tickets": serializer.data,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agent_dashboard(request):
    """
    Agent/admin dashboard: summary of open/closed tickets, response times, performance, etc.
    """
    open_tickets = Ticket.objects.filter(
        status__in=["new", "open", "in_progress", "in-progress", "escalated"]
    ).count()
    closed_tickets = Ticket.objects.filter(status="resolved").count()
    avg_response = TicketInteraction.objects.filter(interaction_type="agent_response").aggregate(avg=Avg("created_at"))
    return Response({
        "open_tickets": open_tickets,
        "closed_tickets": closed_tickets,
        "avg_agent_response_time": avg_response["avg"],
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_update_tickets(request):
    """
    Bulk update tickets (close, assign, etc.).
    Body: {"ticket_ids": [1,2,3], "status": "resolved"}
    """
    ids = request.data.get("ticket_ids", [])
    status_val = request.data.get("status")
    if not ids or not status_val:
        return Response({"error": "ticket_ids and status are required."}, status=400)
    Ticket.objects.filter(ticket_id__in=ids).update(status=status_val)
    return Response({"message": f"Updated {len(ids)} tickets to {status_val}."})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def suggest_kb_articles(request, ticket_id):
    """
    Suggest relevant knowledge base articles for a ticket.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    from knowledge_base.models import KnowledgeBaseArticle
    articles = KnowledgeBaseArticle.objects.filter(category=ticket.category)[:5]
    return Response({"suggestions": [a.title for a in articles]})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_internal_note(request, ticket_id):
    """
    Add a private/internal note to a ticket (visible only to agents).
    Body: {"note": "..."}
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    note = request.data.get("note")
    if not note:
        return Response({"error": "Note is required."}, status=400)
    # Store as a special TicketInteraction type
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.assigned_to or ticket.user,
        interaction_type="agent_response",
        content=f"[INTERNAL NOTE] {note}"
    )
    return Response({"message": "Internal note added."})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log(request, ticket_id):
    """
    Get audit log (all interactions) for a ticket.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    interactions = TicketInteraction.objects.filter(ticket=ticket).order_by("created_at")
    serializer = TicketInteractionSerializer(interactions, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_suggestions(request, ticket_id):
    """
    Get AI-suggested solutions or similar tickets for a ticket.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    # Similar tickets can be from other users (suggestions) - return last 3 resolved in same category
    similar = Ticket.objects.filter(category=ticket.category, status="resolved").exclude(ticket_id=ticket_id)[:3]
    return Response({"similar_tickets": TicketSerializer(similar, many=True).data})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=300)  # Cache for 5 minutes
def agent_analytics(request):
    """
    Get comprehensive AI agent analytics and performance metrics.
    Scoped to current user's tickets (staff see all).
    """
    try:
        # Get total tickets processed by agent
        total_processed = Ticket.objects.filter(agent_processed=True).count()
        total_tickets = Ticket.objects.count()
        processing_rate = (total_processed / total_tickets * 100) if total_tickets > 0 else 0
        
        # Get resolution success rate (tickets with agent_response that were resolved)
        agent_resolved = Ticket.objects.filter(agent_processed=True, status='resolved').count()
        resolution_success_rate = (agent_resolved / total_processed * 100) if total_processed > 0 else 0
        
        # Get average confidence scores from agent responses
        tickets_with_confidence = Ticket.objects.filter(
            agent_processed=True, 
            agent_response__isnull=False
        ).exclude(agent_response={})
        
        total_confidence = 0
        confidence_count = 0
        high_confidence_count = 0
        medium_confidence_count = 0
        low_confidence_count = 0
        
        for ticket in tickets_with_confidence:
            if isinstance(ticket.agent_response, dict):
                confidence = ticket.agent_response.get('confidence', 0)
                if confidence > 0:
                    total_confidence += confidence
                    confidence_count += 1
                    if confidence >= 0.8:
                        high_confidence_count += 1
                    elif confidence >= 0.6:
                        medium_confidence_count += 1
                    else:
                        low_confidence_count += 1
        
        avg_confidence = (total_confidence / confidence_count) if confidence_count > 0 else 0
        
        # Get learning statistics (from auto-learning)
        from knowledge_base.models import KnowledgeBaseArticle
        kb_articles_count = KnowledgeBaseArticle.objects.count()
        recent_kb_articles = KnowledgeBaseArticle.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        
        # Get autonomous actions stats
        from solutions.models import Solution
        auto_solutions_count = Solution.objects.filter(confidence_score__gte=0.8).count()
        
        return Response({
            'total_tickets': total_tickets,
            'processed_by_agent': total_processed,
            'agent_processing_rate': round(processing_rate, 2),
            'resolution_success_rate': round(resolution_success_rate, 2),
            'average_confidence_score': round(avg_confidence, 3),
            'confidence_distribution': {
                'high': high_confidence_count,
                'medium': medium_confidence_count,
                'low': low_confidence_count
            },
            'knowledge_base': {
                'total_articles': kb_articles_count,
                'recent_articles': recent_kb_articles
            },
            'autonomous_solutions': auto_solutions_count,
            'agent_status': 'active',
            'last_updated': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in agent analytics: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve agent analytics', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
def enhanced_kb_search(request):
    """
    Enhanced knowledge base search using FastAPI agent's multi-source search.
    Searches both Django KB and vector store, returns best results.
    """
    try:
        import requests
        
        query = request.data.get('query', '')
        limit = request.data.get('limit', 5)
        category = request.data.get('category')
        min_helpfulness = request.data.get('min_helpfulness')
        
        if not query:
            return Response({'error': 'Query is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Prepare request for FastAPI agent
        agent_url = getattr(settings, 'AI_AGENT_URL', 'http://localhost:8000')
        kb_search_url = f"{agent_url.rstrip('/')}/api/kb/search"
        
        payload = {
            'query': query,
            'limit': limit,
        }
        if category:
            payload['category'] = category
        if min_helpfulness:
            payload['min_helpfulness'] = min_helpfulness
        
        response = requests.post(
            kb_search_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        
        return Response(response.json())
        
    except requests.RequestException as e:
        logger.error(f"Error calling FastAPI agent KB search: {str(e)}")
        # Fallback to local Django KB search
        from knowledge_base.views import KnowledgeBaseArticleViewSet
        from knowledge_base.serializers import KnowledgeBaseArticleSerializer
        
        query = request.data.get('query', '').lower()
        articles = KnowledgeBaseArticle.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )[:limit]
        
        serializer = KnowledgeBaseArticleSerializer(articles, many=True)
        return Response({
            'recommendations': serializer.data,
            'total_matches': articles.count(),
            'sources_used': ['django_kb'],
            'fallback_used': True
        })
    except Exception as e:
        logger.error(f"Error in enhanced KB search: {str(e)}")
        return Response(
            {'error': 'Failed to search knowledge base', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["GET"])
def agent_recommendations(request):
    """
    Get proactive AI recommendations for current ticket backlog and patterns.
    """
    try:
        recommendations = []
        
        # Identify tickets that need attention
        pending_tickets = Ticket.objects.filter(
            status__in=['new', 'open', 'pending']
        ).order_by('-created_at')[:10]
        
        for ticket in pending_tickets:
            recommendation = {
                'ticket_id': ticket.ticket_id,
                'issue_type': ticket.issue_type,
                'description': ticket.description or '',
                'category': ticket.category,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'recommendations': []
            }
            
            # Add recommendations based on agent analysis
            if ticket.agent_response and isinstance(ticket.agent_response, dict):
                confidence = ticket.agent_response.get('confidence', 0)
                recommended_action = ticket.agent_response.get('recommended_action', '')
                
                if confidence >= 0.8:
                    recommendation['recommendations'].append({
                        'type': 'high_confidence_solution',
                        'message': 'High-confidence solution available - can auto-resolve',
                        'action': 'auto_resolve',
                        'confidence': confidence
                    })
                elif confidence >= 0.6:
                    recommendation['recommendations'].append({
                        'type': 'suggested_solution',
                        'message': 'Solution suggestion available for review',
                        'action': 'review_solution',
                        'confidence': confidence
                    })
            
            # Check for similar resolved tickets
            similar = Ticket.objects.filter(
                category=ticket.category,
                status='resolved'
            ).exclude(ticket_id=ticket.ticket_id)[:1]
            
            if similar.exists():
                recommendation['recommendations'].append({
                    'type': 'similar_tickets',
                    'message': f'Found {similar.count()} similar resolved ticket(s)',
                    'action': 'view_similar',
                    'similar_count': similar.count()
                })
            
            if recommendation['recommendations']:
                recommendations.append(recommendation)
        
        return Response({
            'recommendations': recommendations,
            'total_recommendations': len(recommendations),
            'generated_at': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in agent recommendations: {str(e)}")
        return Response(
            {'error': 'Failed to get agent recommendations', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([RollbackThrottle])
def rollback_action(request, action_history_id):
    """
    Rollback an autonomous action (admin/manager only).
    Enables recovery from incorrect agent decisions.
    
    Request body:
    {
        "reason": "Reason for rollback"
    }
    """
    from .rollback import RollbackManager
    
    # Check permissions - only staff and managers can rollback
    if not request.user.is_staff and not hasattr(request.user, 'role'):
        return Response(
            {'error': 'Only admins and managers can rollback actions'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        action_history = ActionHistory.objects.get(id=action_history_id)
        
        # Check if already rolled back
        if action_history.rolled_back:
            return Response(
                {'error': 'This action was already rolled back'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if rollback is supported
        if not RollbackManager.can_rollback(action_history.action_type):
            return Response(
                {'error': f'Action type {action_history.action_type} does not support rollback'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual rollback by admin')
        
        # Execute rollback
        success = RollbackManager.execute_rollback(action_history, request.user, reason)
        
        if success:
            return Response({
                'message': 'Action rolled back successfully',
                'ticket_id': action_history.ticket.ticket_id,
                'action_type': action_history.action_type,
                'rollback_reason': reason,
            })
        else:
            return Response(
                {'error': 'Rollback failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except ActionHistory.DoesNotExist:
        return Response(
            {'error': 'Action history not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in rollback: {str(e)}")
        return Response(
            {'error': 'Rollback failed', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def action_history(request, ticket_id):
    """
    Get action history for a ticket.
    Shows all autonomous actions taken and their rollback status.
    """
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        actions = ActionHistory.objects.filter(ticket=ticket).order_by('-executed_at')
        
        history = []
        for action in actions:
            history.append({
                'id': str(action.id),
                'action_type': action.action_type,
                'executed_at': action.executed_at.isoformat(),
                'executed_by': action.executed_by,
                'confidence_score': action.confidence_score,
                'rollback_possible': action.rollback_possible,
                'rolled_back': action.rolled_back,
                'rolled_back_at': action.rolled_back_at.isoformat() if action.rolled_back_at else None,
                'rollback_reason': action.rollback_reason,
            })
        
        return Response({
            'ticket_id': ticket_id,
            'action_history': history,
            'total_actions': len(history),
        })
        
    except Ticket.DoesNotExist:
        return Response(
            {'error': 'Ticket not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_resolution_feedback(request, ticket_id):
    """
    Submit user feedback on resolution outcome.
    Part of feedback loop validation system.
    
    Request body:
    {
        "resolution_confirmed": true/false,
        "satisfaction_score": 1-5,
        "feedback_text": "optional feedback"
    }
    """
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Get or create resolution tracking
        resolution, created = TicketResolution.objects.get_or_create(
            ticket=ticket,
            defaults={'autonomous_action': 'MANUAL'}
        )
        
        # Update feedback
        resolution.resolution_confirmed = request.data.get('resolution_confirmed')
        resolution.satisfaction_score = request.data.get('satisfaction_score')
        resolution.user_feedback_text = request.data.get('feedback_text', '')
        resolution.response_received_at = timezone.now()
        
        # If user says NOT resolved, reopen ticket
        if resolution.resolution_confirmed is False:
            resolution.reopened = True
            resolution.reopened_at = timezone.now()
            resolution.reopened_reason = request.data.get('feedback_text', 'User reported issue not resolved')
            
            ticket.status = 'escalated'
            ticket.save()
        
        resolution.save()
        
        return Response({
            'message': 'Feedback received successfully',
            'ticket_id': ticket_id,
            'resolution_confirmed': resolution.resolution_confirmed,
            'ticket_reopened': resolution.reopened,
        })
        
    except Ticket.DoesNotExist:
        return Response(
            {'error': 'Ticket not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        return Response(
            {'error': 'Failed to submit feedback', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resolution_analytics(request):
    """
    Get analytics on resolution feedback and success rates.
    Helps validate autonomous agent performance.
    """
    try:
        resolution_qs = TicketResolution.objects.all()
        total_resolutions = resolution_qs.count()
        confirmed_resolutions = resolution_qs.filter(resolution_confirmed=True).count()
        failed_resolutions = resolution_qs.filter(resolution_confirmed=False).count()
        reopened_tickets = resolution_qs.filter(reopened=True).count()
        
        # Average satisfaction score
        avg_satisfaction = resolution_qs.filter(
            satisfaction_score__isnull=False
        ).aggregate(avg=Avg('satisfaction_score'))['avg']
        
        # Success rate by action type
        from django.db import models as django_models
        action_types = resolution_qs.values('autonomous_action').annotate(
            total=Count('id'),
            confirmed=Count('id', filter=django_models.Q(resolution_confirmed=True)),
            failed=Count('id', filter=django_models.Q(resolution_confirmed=False))
        )
        
        return Response({
            'total_resolutions': total_resolutions,
            'confirmed_successful': confirmed_resolutions,
            'confirmed_failed': failed_resolutions,
            'reopened_tickets': reopened_tickets,
            'average_satisfaction_score': round(avg_satisfaction, 2) if avg_satisfaction else None,
            'success_rate': round((confirmed_resolutions / total_resolutions * 100), 2) if total_resolutions > 0 else 0,
            'action_type_breakdown': list(action_types),
        })
        
    except Exception as e:
        logger.error(f"Error in resolution analytics: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve analytics', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --- Documentation for all endpoints ---
"""
API Endpoints for Ticket Management (Web Portal)
===============================================

1. POST   /api/tickets/                       - Create a new ticket
2. GET    /api/tickets/                       - List all tickets (optionally filter by user/status)
3. GET    /api/tickets/<ticket_id>/           - Get details for a single ticket
4. PATCH  /api/tickets/<ticket_id>/           - Update ticket status/details
5. POST   /api/tickets/<ticket_id>/clarify/   - Add clarification to a ticket
6. POST   /api/tickets/<ticket_id>/feedback/  - Add feedback to a ticket
7. GET    /api/tickets/<ticket_id>/history/   - Get recent ticket interactions (history)
8. GET    /api/tickets/analytics/             - Ticket analytics
9. POST   /api/tickets/<ticket_id>/process/   - Manually trigger agent processing
10. GET   /api/tickets/tasks/<task_id>/status/ - Get Celery task status
11. GET   /api/tickets/<ticket_id>/agent-status/ - Get agent processing status and history
12. GET   /api/tickets/search/                 - Search and filter tickets
13. POST  /api/tickets/<ticket_id>/upload/    - Upload an attachment to a ticket
14. POST  /api/tickets/<ticket_id>/comment/   - Add a comment to a ticket
15. POST  /api/tickets/<ticket_id>/escalate/  - Escalate a ticket
16. POST  /api/tickets/<ticket_id>/assign/    - Assign a ticket to an agent
17. POST  /api/tickets/<ticket_id>/status/    - Update ticket status
18. GET   /api/tickets/agent-dashboard/        - Agent/admin dashboard
19. POST  /api/tickets/bulk-update/           - Bulk update tickets
20. GET   /api/tickets/<ticket_id>/kb-suggestions/ - Suggest knowledge base articles
21. POST  /api/tickets/<ticket_id>/internal-note/ - Add an internal note to a ticket
22. GET   /api/tickets/<ticket_id>/audit-log/ - Get audit log for a ticket
23. GET   /api/tickets/<ticket_id>/ai-suggestions/ - Get AI suggestions for a ticket

All endpoints return JSON responses. Authentication/permissions can be added as needed.
"""
