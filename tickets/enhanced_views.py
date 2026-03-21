"""
Enhanced API views for improved UX/UI performance
Implements Quick Wins from BACKEND_ENHANCEMENT_REQUESTS.md
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import timedelta

from .models import Ticket, ActionHistory
from .serializers import ActionHistorySerializer
from .cache_decorators import cache_api_response, no_cache
from knowledge_base.models import KnowledgeBaseArticle

import logging

logger = logging.getLogger(__name__)


class ActionHistoryPagination(PageNumberPagination):
    """Custom pagination for action history"""
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=60)  # Cache for 1 minute
def paginated_action_history(request, ticket_id):
    """
    Get paginated action history for a ticket.
    
    Query params:
        - page: Page number (default: 1)
        - limit: Items per page (default: 20, max: 100)
        - sort: Sort order - 'desc' or 'asc' (default: desc)
    
    Example: GET /api/tickets/42/action-history-paginated/?page=1&limit=20&sort=desc
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)

    # Get sort parameter
    sort_order = request.query_params.get('sort', 'desc')
    order_by = '-executed_at' if sort_order == 'desc' else 'executed_at'
    
    # Get action history queryset
    action_history = ActionHistory.objects.filter(ticket=ticket).order_by(order_by)
    
    # Paginate
    paginator = ActionHistoryPagination()
    paginated_history = paginator.paginate_queryset(action_history, request)
    
    # Serialize
    serializer = ActionHistorySerializer(paginated_history, many=True)
    
    # Return paginated response
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=300)  # Cache for 5 minutes
def dashboard_summary(request):
    """
    Aggregated dashboard metrics in a single API call.
    Reduces frontend API calls from 5+ to 1.
    
    Returns:
        - Total tickets and agent-processed count  
        - Pending recommendations count
        - High confidence recommendations
        - Resolution trends (last 7 days)
        - Top categories
        - Agent performance metrics
    
    Example: GET /api/tickets/agent/dashboard-summary/
    """
    try:
        base_qs = Ticket.objects.all()
        # Basic metrics
        total_tickets = base_qs.count()
        processed_by_agent = base_qs.filter(agent_processed=True).count()
        
        # Pending review (agent processed but not resolved)
        pending_review = base_qs.filter(
            agent_processed=True,
            status__in=['new', 'open', 'in_progress']
        ).count()
        
        # High confidence tickets (confidence >= 0.8)
        high_confidence_tickets = []
        tickets_with_confidence = base_qs.filter(
            agent_processed=True,
            agent_response__isnull=False,
            status__in=['new', 'open', 'in_progress']
        ).exclude(agent_response={})[:50]  # Limit for performance
        
        for ticket in tickets_with_confidence:
            if isinstance(ticket.agent_response, dict):
                confidence = ticket.agent_response.get('confidence', 0)
                if confidence >= 0.8:
                    high_confidence_tickets.append({
                        'ticket_id': ticket.ticket_id,
                        'issue_type': ticket.issue_type,
                        'confidence': confidence,
                        'recommended_action': ticket.agent_response.get('recommended_action'),
                        'created_at': ticket.created_at.isoformat()
                    })
        
        # Resolution trends (last 7 days)
        resolution_trends = []
        trend_labels = []
        today = timezone.now().date()
        
        for i in range(6, -1, -1):  # Last 7 days
            day = today - timedelta(days=i)
            count = base_qs.filter(
                agent_processed=True,
                status='resolved',
                updated_at__date=day
            ).count()
            resolution_trends.append(count)
            trend_labels.append(day.strftime('%a'))  # Mon, Tue, etc.
        
        # Top categories
        top_categories = list(
            base_qs.filter(agent_processed=True)
            .values('category')
            .annotate(count=Count('ticket_id'))
            .order_by('-count')[:5]
        )
        
        # Agent performance metrics
        agent_resolved = base_qs.filter(
            agent_processed=True,
            status='resolved'
        ).count()
        resolution_rate = (agent_resolved / processed_by_agent * 100) if processed_by_agent > 0 else 0
        
        # Average confidence
        total_confidence = 0
        confidence_count = 0
        for ticket in base_qs.filter(agent_processed=True, agent_response__isnull=False):
            if isinstance(ticket.agent_response, dict):
                conf = ticket.agent_response.get('confidence', 0)
                if conf > 0:
                    total_confidence += conf
                    confidence_count += 1
        
        avg_confidence = (total_confidence / confidence_count) if confidence_count > 0 else 0
        
        # Recent recommendations (last 10)
        recent_recommendations = []
        recent_tickets = base_qs.filter(
            agent_processed=True,
            agent_response__isnull=False
        ).order_by('-updated_at')[:10]
        
        for ticket in recent_tickets:
            if isinstance(ticket.agent_response, dict):
                recent_recommendations.append({
                    'ticket_id': ticket.ticket_id,
                    'issue_type': ticket.issue_type,
                    'status': ticket.status,
                    'confidence': ticket.agent_response.get('confidence', 0),
                    'recommended_action': ticket.agent_response.get('recommended_action'),
                    'updated_at': ticket.updated_at.isoformat()
                })
        
        # KB articles count
        kb_articles_total = KnowledgeBaseArticle.objects.count()
        kb_articles_recent = KnowledgeBaseArticle.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        return Response({
            'metrics': {
                'total_tickets': total_tickets,
                'processed_by_agent': processed_by_agent,
                'pending_review': pending_review,
                'high_confidence_count': len(high_confidence_tickets),
                'resolution_rate': round(resolution_rate, 2),
                'avg_confidence': round(avg_confidence, 2),
            },
            'high_confidence_tickets': high_confidence_tickets[:5],  # Top 5
            'recent_recommendations': recent_recommendations,
            'resolution_trends': {
                'data': resolution_trends,
                'labels': trend_labels
            },
            'top_categories': top_categories,
            'knowledge_base': {
                'total_articles': kb_articles_total,
                'recent_articles_30d': kb_articles_recent
            },
            'generated_at': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Dashboard summary error: {str(e)}")
        return Response(
            {'error': 'Failed to generate dashboard summary'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=120)  # Cache for 2 minutes
def filtered_recommendations(request):
    """
    Get AI recommendations with smart filtering.
    
    Query params:
        - confidence_min: Minimum confidence (0.0-1.0)
        - confidence_max: Maximum confidence (0.0-1.0)
        - action_type: Filter by recommended_action (AUTO_RESOLVE, ESCALATE, etc.)
        - priority: Filter by priority (low, medium, high, critical) - comma-separated
        - category: Filter by category
        - status: Filter by status (new, open, in_progress, etc.) - comma-separated
        - created_after: ISO date string
        - created_before: ISO date string
        - sort_by: Sort field (confidence_desc, confidence_asc, created_desc, created_asc)
        - limit: Max results (default: 50, max: 200)
    
    Example: GET /api/tickets/agent/recommendations/?confidence_min=0.8&action_type=AUTO_RESOLVE&sort_by=confidence_desc
    """
    try:
        # Base queryset - tickets processed by agent (not yet resolved)
        queryset = Ticket.objects.filter(
            agent_processed=True,
            agent_response__isnull=False
        ).exclude(agent_response={})
        
        # Confidence filters
        confidence_min = request.query_params.get('confidence_min')
        confidence_max = request.query_params.get('confidence_max')
        
        # Status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(',')]
            queryset = queryset.filter(status__in=statuses)
        else:
            # Default: not resolved
            queryset = queryset.exclude(status='resolved')
        
        # Category filter
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Date filters
        created_after = request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        created_before = request.query_params.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        # Get tickets
        tickets = queryset.order_by('-updated_at')
        
        # Build recommendations list with filtering
        recommendations = []
        action_type_filter = request.query_params.get('action_type')
        
        for ticket in tickets:
            if not isinstance(ticket.agent_response, dict):
                continue
            
            confidence = ticket.agent_response.get('confidence', 0)
            recommended_action = ticket.agent_response.get('recommended_action', '')
            
            # Apply confidence filters
            if confidence_min and confidence < float(confidence_min):
                continue
            if confidence_max and confidence > float(confidence_max):
                continue
            
            # Apply action type filter
            if action_type_filter and recommended_action != action_type_filter:
                continue
            
            recommendations.append({
                'ticket_id': ticket.ticket_id,
                'issue_type': ticket.issue_type,
                'description': ticket.description[:200],  # Truncated
                'category': ticket.category,
                'status': ticket.status,
                'confidence': confidence,
                'recommended_action': recommended_action,
                'analysis': ticket.agent_response.get('analysis', {}),
                'solution': ticket.agent_response.get('solution', {}),
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat(),
            })
        
        # Sort
        sort_by = request.query_params.get('sort_by', 'confidence_desc')
        if sort_by == 'confidence_desc':
            recommendations.sort(key=lambda x: x['confidence'], reverse=True)
        elif sort_by == 'confidence_asc':
            recommendations.sort(key=lambda x: x['confidence'])
        elif sort_by == 'created_desc':
            recommendations.sort(key=lambda x: x['created_at'], reverse=True)
        elif sort_by == 'created_asc':
            recommendations.sort(key=lambda x: x['created_at'])
        
        # Limit
        limit = int(request.query_params.get('limit', 50))
        limit = min(limit, 200)  # Max 200
        recommendations = recommendations[:limit]
        
        return Response({
            'recommendations': recommendations,
            'count': len(recommendations),
            'filters_applied': {
                'confidence_min': confidence_min,
                'confidence_max': confidence_max,
                'action_type': action_type_filter,
                'status': status_filter,
                'category': category,
                'sort_by': sort_by,
            }
        })
        
    except Exception as e:
        logger.error(f"Filtered recommendations error: {str(e)}")
        return Response(
            {'error': 'Failed to get recommendations'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# Batch Operations API (P0 Priority)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@no_cache
def batch_process_tickets(request):
    """
    Process multiple tickets with AI agent in a single request.
    Creates a batch job and processes tickets asynchronously.
    
    Request body:
        {
            "ticket_ids": [42, 43, 44],
            "action": "process" | "accept" | "reject",
            "force": false  # Optional: force re-processing
        }
    
    Response:
        {
            "batch_id": "uuid",
            "total": 3,
            "status": "processing",
            "tickets": [42, 43, 44]
        }
    
    Example: POST /api/tickets/agent/batch-process/
    """
    try:
        ticket_ids = request.data.get('ticket_ids', [])
        action = request.data.get('action', 'process')
        force = request.data.get('force', False)
        
        if not ticket_ids:
            return Response(
                {'error': 'ticket_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(ticket_ids, list):
            return Response(
                {'error': 'ticket_ids must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if action not in ['process', 'accept', 'reject']:
            return Response(
                {'error': 'action must be one of: process, accept, reject'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify tickets exist
        tickets = Ticket.objects.filter(ticket_id__in=ticket_ids)
        if tickets.count() != len(ticket_ids):
            return Response(
                {'error': 'Some ticket IDs are invalid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create batch job
        from .tasks import batch_process_tickets as batch_task
        import uuid
        batch_id = str(uuid.uuid4())
        
        # Queue batch task
        task = batch_task.delay(batch_id, ticket_ids, action, force)
        
        return Response({
            'batch_id': batch_id,
            'task_id': task.id,
            'total': len(ticket_ids),
            'status': 'processing',
            'tickets': ticket_ids,
            'action': action
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Batch process error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_status(request, batch_id):
    """
    Get status of a batch operation.
    
    Response:
        {
            "batch_id": "uuid",
            "total": 3,
            "completed": 2,
            "failed": 0,
            "in_progress": 1,
            "results": [
                {
                    "ticket_id": 42,
                    "status": "completed",
                    "success": true
                },
                ...
            ]
        }
    
    Example: GET /api/tickets/agent/batch/{batch_id}/status/
    """
    try:
        # Get batch results from cache
        from django.core.cache import cache
        batch_data = cache.get(f'batch_{batch_id}')
        
        if not batch_data:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(batch_data)
        
    except Exception as e:
        logger.error(f"Batch status error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@no_cache
def validate_action(request, ticket_id):
    """
    Validate an action before executing (for optimistic UI).
    
    Request body:
        {
            "action_type": "AUTO_RESOLVE",
            "solution_data": {...}
        }
    
    Response:
        {
            "valid": true,
            "conflicts": [],
            "estimated_duration": "5 seconds",
            "preview": {
                "changes": [
                    {"field": "status", "from": "open", "to": "resolved"}
                ]
            }
        }
    
    Example: POST /api/tickets/{ticket_id}/actions/validate/
    """
    try:
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
        action_type = request.data.get('action_type')
        
        if not action_type:
            return Response(
                {'error': 'action_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        conflicts = []
        changes = []
        valid = True
        
        # Check for conflicts
        if action_type == 'AUTO_RESOLVE':
            if ticket.status == 'resolved':
                conflicts.append('Ticket is already resolved')
                valid = False
            else:
                changes.append({
                    'field': 'status',
                    'from': ticket.status,
                    'to': 'resolved'
                })
        
        elif action_type == 'ESCALATE':
            if ticket.status == 'escalated':
                conflicts.append('Ticket is already escalated')
                valid = False
            else:
                changes.append({
                    'field': 'status',
                    'from': ticket.status,
                    'to': 'escalated'
                })
        
        return Response({
            'valid': valid,
            'conflicts': conflicts,
            'estimated_duration': '5 seconds',
            'preview': {
                'changes': changes,
                'affected_users': [ticket.user.email] if hasattr(ticket.user, 'email') else [],
                'reversible': action_type != 'DELETE'
            }
        })
        
    except Exception as e:
        logger.error(f"Action validation error: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
