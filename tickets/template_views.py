"""
Views for Resolution Template management.
Handles CRUD operations and template application.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q

from tickets.models import ResolutionTemplate, Ticket, ActionHistory
from tickets.serializers import (
    ResolutionTemplateSerializer,
    ResolutionTemplateListSerializer,
    ApplyTemplateSerializer
)
from tickets.cache_decorators import cache_api_response, no_cache


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=300)
def list_resolution_templates(request):
    """
    List all resolution templates with optional filtering.
    
    Query Parameters:
    - category: Filter by category (e.g., 'email', 'network')
    - issue_type: Filter by issue type
    - is_active: Filter by active status (true/false)
    - search: Search in name and description
    - sort_by: Sort field (use_count, success_rate, created_at)
    - limit: Max results to return (default: all)
    """
    queryset = ResolutionTemplate.objects.filter(is_active=True)
    
    # Apply filters
    category = request.GET.get('category')
    if category:
        queryset = queryset.filter(category=category)
    
    issue_type = request.GET.get('issue_type')
    if issue_type:
        queryset = queryset.filter(issue_types__contains=[issue_type])
    
    is_active = request.GET.get('is_active')
    if is_active is not None:
        is_active_bool = is_active.lower() == 'true'
        queryset = queryset.filter(is_active=is_active_bool)
    
    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search) |
            Q(tags__contains=[search])
        )
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'use_count')
    
    if sort_by == 'success_rate':
        # Sort by success rate (calculated field)
        # PostgreSQL: use raw SQL or Python sorting
        templates = list(queryset)
        templates.sort(key=lambda t: t.success_rate, reverse=True)
        
        limit = request.GET.get('limit')
        if limit:
            try:
                templates = templates[:int(limit)]
            except ValueError:
                pass
        
        serializer = ResolutionTemplateListSerializer(templates, many=True)
        return Response({
            'templates': serializer.data,
            'count': len(serializer.data)
        })
    
    elif sort_by == 'use_count':
        queryset = queryset.order_by('-use_count', '-created_at')
    elif sort_by == 'created_at':
        queryset = queryset.order_by('-created_at')
    else:
        queryset = queryset.order_by('-use_count')
    
    # Limit results
    limit = request.GET.get('limit')
    if limit:
        try:
            queryset = queryset[:int(limit)]
        except ValueError:
            pass
    
    serializer = ResolutionTemplateListSerializer(queryset, many=True)
    
    return Response({
        'templates': serializer.data,
        'count': len(serializer.data)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_resolution_template(request, template_id):
    """
    Get detailed information about a specific resolution template.
    """
    template = get_object_or_404(ResolutionTemplate, id=template_id)
    serializer = ResolutionTemplateSerializer(template)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@no_cache
def create_resolution_template(request):
    """
    Create a new resolution template.
    
    Required fields:
    - name: Template name
    - description: Description
    - category: Category (email, network, etc.)
    - steps: Array of resolution steps
    
    Optional fields:
    - issue_types: List of applicable issue types
    - tags: List of tags
    - estimated_time: Time estimate (default: "10 minutes")
    - custom_params: Custom parameters
    """
    serializer = ResolutionTemplateSerializer(data=request.data)
    
    if serializer.is_valid():
        template = serializer.save(created_by=request.user)
        return Response(
            ResolutionTemplateSerializer(template).data,
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@no_cache
def update_resolution_template(request, template_id):
    """
    Update an existing resolution template.
    """
    template = get_object_or_404(ResolutionTemplate, id=template_id)
    
    serializer = ResolutionTemplateSerializer(
        template,
        data=request.data,
        partial=(request.method == 'PATCH')
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@no_cache
def delete_resolution_template(request, template_id):
    """
    Soft delete a resolution template (set is_active=False).
    """
    template = get_object_or_404(ResolutionTemplate, id=template_id)
    template.is_active = False
    template.save()
    
    return Response({
        'message': 'Template deactivated successfully',
        'template_id': str(template_id)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@no_cache
def apply_template_to_ticket(request, ticket_id):
    """
    Apply a resolution template to a ticket.
    
    Body:
    {
        "template_id": "uuid",
        "custom_params": {...}  // Optional
    }
    
    This creates an action history entry and updates the ticket
    with the template's solution steps.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Validate input
    serializer = ApplyTemplateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    template_id = serializer.validated_data['template_id']
    custom_params = serializer.validated_data.get('custom_params', {})
    
    # Get template
    template = get_object_or_404(ResolutionTemplate, id=template_id, is_active=True)
    
    # Check if template is suitable for this ticket
    if template.category != ticket.category and ticket.category != 'other':
        return Response({
            'error': 'Template category mismatch',
            'template_category': template.category,
            'ticket_category': ticket.category
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Store ticket's current state
    before_state = {
        'status': ticket.status,
        'description': ticket.description,
        'agent_response': ticket.agent_response
    }
    
    # Build resolution data
    resolution_data = {
        'template_id': str(template.id),
        'template_name': template.name,
        'steps': template.steps,
        'estimated_time': template.estimated_time,
        'custom_params': custom_params
    }
    
    # Update ticket with template resolution
    ticket.agent_response = {
        'analysis': {
            'category': template.category,
            'severity': 'medium',
            'complexity': 'low',
            'source': 'resolution_template'
        },
        'recommended_action': 'APPLY_TEMPLATE',
        'confidence': template.success_rate / 100.0 if template.success_rate > 0 else 0.5,
        'solution': resolution_data,
        'reasoning': f"Applied resolution template: {template.name}"
    }
    ticket.agent_processed = True
    ticket.save()
    
    # Store after state
    after_state = {
        'status': ticket.status,
        'description': ticket.description,
        'agent_response': ticket.agent_response
    }
    
    # Create action history entry
    ActionHistory.objects.create(
        ticket=ticket,
        action_type='APPLY_TEMPLATE',
        action_params={
            'template_id': str(template.id),
            'template_name': template.name,
            'custom_params': custom_params
        },
        executed_by=request.user.username,
        confidence_score=template.success_rate / 100.0 if template.success_rate > 0 else 0.5,
        agent_reasoning=f"Applied template '{template.name}' with {template.use_count} previous uses and {template.success_rate}% success rate",
        rollback_possible=True,
        rollback_steps={
            'action': 'restore_previous_state',
            'previous_agent_response': before_state['agent_response']
        },
        before_state=before_state,
        after_state=after_state
    )
    
    # Increment template usage (we'll mark as successful when ticket is resolved)
    template.increment_usage(success=False)  # Success tracked later
    
    return Response({
        'message': 'Template applied successfully',
        'ticket_id': ticket_id,
        'template_id': str(template.id),
        'template_name': template.name,
        'resolution': resolution_data,
        'confidence': template.success_rate / 100.0 if template.success_rate > 0 else 0.5
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=120)
def get_templates_for_ticket(request, ticket_id):
    """
    Get recommended templates for a specific ticket based on category and issue type.
    
    Returns templates sorted by relevance and success rate.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Find templates matching the ticket's category
    queryset = ResolutionTemplate.objects.filter(
        category=ticket.category,
        is_active=True
    )
    
    # If ticket has specific issue type, prioritize matching templates
    if ticket.issue_type:
        # Try exact match first
        exact_matches = queryset.filter(issue_types__contains=[ticket.issue_type])
        if exact_matches.exists():
            queryset = exact_matches
    
    # Sort by success rate and usage
    templates = list(queryset)
    templates.sort(key=lambda t: (t.success_rate, t.use_count), reverse=True)
    
    # Limit to top 10
    templates = templates[:10]
    
    serializer = ResolutionTemplateListSerializer(templates, many=True)
    
    return Response({
        'ticket_id': ticket_id,
        'ticket_category': ticket.category,
        'ticket_issue_type': ticket.issue_type,
        'recommended_templates': serializer.data,
        'count': len(serializer.data)
    })
