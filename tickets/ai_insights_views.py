"""
AI Insights and Transparency Views.
Provides explanations for AI decisions and confidence scores.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count

from tickets.models import Ticket
from solutions.models import KnowledgeBaseEntry
from tickets.cache_decorators import cache_api_response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=180)
def get_confidence_explanation(request, ticket_id):
    """
    Get a detailed explanation of the AI's confidence score for a ticket.
    
    Returns factors that contributed to the confidence score and their impact.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if not ticket.agent_processed or not ticket.agent_response:
        return Response({
            'error': 'Ticket has not been processed by AI agent yet',
            'ticket_id': ticket_id
        }, status=400)
    
    agent_response = ticket.agent_response
    confidence = agent_response.get('confidence', 0.0)
    
    # Build explanation factors
    factors = []
    
    # Factor 1: Similar resolved tickets
    similar_tickets = Ticket.objects.filter(
        category=ticket.category,
        status='resolved',
        agent_processed=True
    ).exclude(ticket_id=ticket_id)
    
    similar_count = similar_tickets.count()
    if similar_count > 0:
        impact = min(0.35, (similar_count / 100) * 0.35)  # Max 35% impact
        factors.append({
            'factor': 'similar_resolved_tickets',
            'impact': round(impact, 2),
            'description': f'{similar_count} similar tickets in category "{ticket.category}" have been resolved',
            'details': {
                'count': similar_count,
                'category': ticket.category
            }
        })
    
    # Factor 2: KB Article Match
    if agent_response.get('knowledge_base'):
        kb_articles = agent_response['knowledge_base'].get('relevant_articles', [])
        if kb_articles:
            # Check relevance scores
            high_relevance = sum(1 for article in kb_articles if article.get('relevance', 0) > 0.7)
            
            if high_relevance > 0:
                impact = min(0.25, (high_relevance / 5) * 0.25)  # Max 25% impact
                factors.append({
                    'factor': 'kb_article_match',
                    'impact': round(impact, 2),
                    'description': f'{high_relevance} highly relevant knowledge base article(s) found',
                    'details': {
                        'high_relevance_count': high_relevance,
                        'total_articles': len(kb_articles),
                        'articles': [
                            {
                                'id': article.get('article_id'),
                                'title': article.get('title', 'Untitled'),
                                'relevance': article.get('relevance', 0)
                            }
                            for article in kb_articles[:3]  # Top 3
                        ]
                    }
                })
    
    # Factor 3: Clear Issue Description
    description_length = len(ticket.description or '')
    if description_length > 50:
        # Longer, detailed descriptions lead to better analysis
        impact = min(0.15, (description_length / 500) * 0.15)  # Max 15% impact
        factors.append({
            'factor': 'clear_issue_description',
            'impact': round(impact, 2),
            'description': 'Issue description is detailed and clear',
            'details': {
                'description_length': description_length,
                'has_details': description_length > 100
            }
        })
    
    # Factor 4: Historical Success Rate (category-based)
    if agent_response.get('solution'):
        # Check if similar solutions have worked before
        category_success = Ticket.objects.filter(
            category=ticket.category,
            status='resolved',
            agent_processed=True
        ).count()
        
        category_total = Ticket.objects.filter(
            category=ticket.category,
            agent_processed=True
        ).count()
        
        if category_total > 0:
            success_rate = category_success / category_total
            impact = round(success_rate * 0.15, 2)  # Max 15% impact
            
            factors.append({
                'factor': 'historical_success',
                'impact': impact,
                'description': f'This solution type has {int(success_rate * 100)}% success rate in "{ticket.category}" category',
                'details': {
                    'success_count': category_success,
                    'total_count': category_total,
                    'success_rate': round(success_rate, 2),
                    'category': ticket.category
                }
            })
    
    # Factor 5: Pattern Recognition
    analysis = agent_response.get('analysis', {})
    complexity = analysis.get('complexity', 'unknown')
    
    if complexity in ['low', 'very_low']:
        factors.append({
            'factor': 'low_complexity',
            'impact': 0.10,
            'description': 'Issue identified as low complexity',
            'details': {
                'complexity': complexity,
                'category': analysis.get('category', 'unknown')
            }
        })
    
    # Factor 6: Agent Certainty Keywords
    reasoning = agent_response.get('reasoning', '')
    certainty_keywords = ['clearly', 'definitely', 'obvious', 'straightforward', 'common', 'standard']
    
    certainty_score = sum(1 for keyword in certainty_keywords if keyword in reasoning.lower())
    if certainty_score > 0:
        impact = min(0.10, certainty_score * 0.03)
        factors.append({
            'factor': 'agent_certainty',
            'impact': round(impact, 2),
            'description': 'AI agent expressed high certainty in analysis',
            'details': {
                'certainty_keywords_found': certainty_score,
                'reasoning_excerpt': reasoning[:200] + '...' if len(reasoning) > 200 else reasoning
            }
        })
    
    # Sort factors by impact (descending)
    factors.sort(key=lambda x: x['impact'], reverse=True)
    
    # Calculate total explained impact
    total_impact = sum(f['impact'] for f in factors)
    
    # Add unexplained factors if there's a gap
    unexplained = confidence - total_impact
    if unexplained > 0.05:  # If more than 5% unexplained
        factors.append({
            'factor': 'other_factors',
            'impact': round(unexplained, 2),
            'description': 'Other AI model considerations',
            'details': {
                'note': 'This includes internal model weights and contextual factors'
            }
        })
    
    return Response({
        'ticket_id': ticket_id,
        'confidence': confidence,
        'total_impact_explained': round(total_impact, 2),
        'factors': factors,
        'breakdown': {
            'high_confidence_threshold': 0.80,
            'medium_confidence_threshold': 0.60,
            'current_confidence_level': (
                'high' if confidence >= 0.80 else
                'medium' if confidence >= 0.60 else
                'low'
            )
        },
        'recommendations': {
            'can_auto_resolve': confidence >= 0.85,
            'needs_review': confidence < 0.70,
            'message': (
                'High confidence - safe for auto-resolution' if confidence >= 0.85 else
                'Medium confidence - recommend review before execution' if confidence >= 0.70 else
                'Low confidence - manual review required'
            )
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_api_response(max_age=300)
def get_similar_tickets(request, ticket_id):
    """
    Find similar tickets based on category, issue_type, and description.
    
    Query Parameters:
    - limit: Max results to return (default: 5, max: 20)
    - threshold: Similarity threshold 0.0-1.0 (default: 0.7)
    - status: Filter by status (e.g., 'resolved')
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    limit = int(request.GET.get('limit', 5))
    limit = min(limit, 20)  # Max 20 results
    
    threshold = float(request.GET.get('threshold', 0.7))
    status_filter = request.GET.get('status', 'resolved')
    
    # Find similar tickets
    queryset = Ticket.objects.exclude(ticket_id=ticket_id)
    
    # Filter by status if provided
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    # Start with same category (high similarity)
    similar_tickets = list(queryset.filter(category=ticket.category)[:limit * 2])
    
    # Calculate similarity scores
    scored_tickets = []
    
    for similar_ticket in similar_tickets:
        score = 0.0
        
        # Category match (30%)
        if similar_ticket.category == ticket.category:
            score += 0.30
        
        # Issue type similarity (30%)
        if ticket.issue_type and similar_ticket.issue_type:
            # Simple keyword matching
            ticket_keywords = set(ticket.issue_type.lower().split())
            similar_keywords = set(similar_ticket.issue_type.lower().split())
            
            if ticket_keywords and similar_keywords:
                keyword_overlap = len(ticket_keywords & similar_keywords) / len(ticket_keywords | similar_keywords)
                score += keyword_overlap * 0.30
        
        # Description similarity (20%)
        if ticket.description and similar_ticket.description:
            ticket_desc_words = set(ticket.description.lower().split())
            similar_desc_words = set(similar_ticket.description.lower().split())
            
            if ticket_desc_words and similar_desc_words:
                desc_overlap = len(ticket_desc_words & similar_desc_words) / len(ticket_desc_words | similar_desc_words)
                score += desc_overlap * 0.20
        
        # Same assigned team/person (10%)
        if ticket.assigned_to and similar_ticket.assigned_to:
            if ticket.assigned_to == similar_ticket.assigned_to:
                score += 0.10
        
        # Tags overlap (10%)
        if ticket.tags and similar_ticket.tags:
            ticket_tags = set(ticket.tags)
            similar_tags = set(similar_ticket.tags)
            
            if ticket_tags and similar_tags:
                tag_overlap = len(ticket_tags & similar_tags) / len(ticket_tags | similar_tags)
                score += tag_overlap * 0.10
        
        # Only include if above threshold
        if score >= threshold:
            # Calculate resolution time if resolved
            resolution_time = None
            if similar_ticket.status == 'resolved' and similar_ticket.updated_at and similar_ticket.created_at:
                delta = similar_ticket.updated_at - similar_ticket.created_at
                minutes = int(delta.total_seconds() / 60)
                
                if minutes < 60:
                    resolution_time = f"{minutes} min"
                elif minutes < 1440:  # Less than a day
                    hours = minutes // 60
                    resolution_time = f"{hours} hr{'s' if hours > 1 else ''}"
                else:
                    days = minutes // 1440
                    resolution_time = f"{days} day{'s' if days > 1 else ''}"
            
            scored_tickets.append({
                'ticket_id': similar_ticket.ticket_id,
                'similarity_score': round(score, 2),
                'issue_type': similar_ticket.issue_type,
                'category': similar_ticket.category,
                'status': similar_ticket.status,
                'description': similar_ticket.description[:200] + '...' if len(similar_ticket.description or '') > 200 else similar_ticket.description,
                'resolution': similar_ticket.agent_response.get('solution') if similar_ticket.agent_response else None,
                'created_at': similar_ticket.created_at.isoformat(),
                'resolved_at': similar_ticket.updated_at.isoformat() if similar_ticket.status == 'resolved' else None,
                'resolution_time': resolution_time,
                'confidence': similar_ticket.agent_response.get('confidence') if similar_ticket.agent_response else None
            })
    
    # Sort by similarity score
    scored_tickets.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    # Limit results
    scored_tickets = scored_tickets[:limit]
    
    return Response({
        'ticket_id': ticket_id,
        'similar_tickets': scored_tickets,
        'count': len(scored_tickets),
        'filters': {
            'threshold': threshold,
            'limit': limit,
            'status': status_filter
        }
    })
