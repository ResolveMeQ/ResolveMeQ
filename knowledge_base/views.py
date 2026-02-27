from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from .models import KnowledgeBaseArticle, LLMResponse
from .serializers import KnowledgeBaseArticleSerializer, LLMResponseSerializer
from .services import KnowledgeBaseService
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

class KnowledgeBaseArticleViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeBaseArticle.objects.all()
    serializer_class = KnowledgeBaseArticleSerializer
    permission_classes = [AllowAny]  # Allow public access for FastAPI agent
    lookup_field = 'kb_id'

    @action(detail=False, methods=['post'])
    def search(self, request):
        query = request.data.get('query', '').lower()
        if not query:
            return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        # SQLite-compatible search: filter in Python for tags
        articles = [a for a in self.queryset if (
            query in a.title.lower() or
            query in a.content.lower() or
            any(query in str(tag).lower() for tag in a.tags)
        )]
        articles = sorted(articles, key=lambda a: (-a.views, -a.helpful_votes))
        serializer = self.get_serializer(articles, many=True)
        return Response({'results': serializer.data})

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(content__icontains=q)
            )
        tags = self.request.query_params.get('tags')
        if tags:
            tag = tags.lower()
            queryset = [a for a in queryset if tag in [str(t).lower() for t in (a.tags or [])]]
        return queryset

    @action(detail=True, methods=['post'])
    def rate(self, request, kb_id=None):
        article = self.get_object()
        is_helpful = request.data.get('is_helpful', None)
        
        if is_helpful is None:
            return Response({'error': 'is_helpful parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        article.total_votes += 1
        if is_helpful:
            article.helpful_votes += 1
        article.save()

        return Response({'status': 'success'})

class LLMResponseViewSet(viewsets.ModelViewSet):
    queryset = LLMResponse.objects.all()
    serializer_class = LLMResponseSerializer
    permission_classes = [AllowAny]  # Allow public access for FastAPI agent
    lookup_field = 'response_id'

    def create(self, request, *args, **kwargs):
        try:
            response = KnowledgeBaseService.store_llm_response(
                query=request.data.get('query'),
                response=request.data.get('response'),
                response_type=request.data.get('response_type'),
                ticket=request.data.get('ticket'),
                related_kb_articles=request.data.get('related_kb_articles')
            )
            serializer = self.get_serializer(response)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating LLM response: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def rate(self, request, response_id=None):
        try:
            response = self.get_object()
            is_helpful = request.data.get('is_helpful')
            
            if is_helpful is None:
                return Response({'error': 'is_helpful parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

            updated_response = KnowledgeBaseService.update_response_rating(response.response_id, is_helpful)
            serializer = self.get_serializer(updated_response)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error rating LLM response: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def search(self, request):
        query = request.data.get('query', '')
        if not query:
            return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        responses = KnowledgeBaseService.get_related_responses(query)
        serializer = self.get_serializer(responses, many=True)
        return Response({'results': serializer.data})

# API endpoints for FastAPI agent access
@api_view(['GET'])
@permission_classes([AllowAny])  # You can add authentication later
def kb_articles_for_agent(request):
    """
    Public API endpoint for FastAPI agent to access Knowledge Base articles.
    Returns all articles with basic fields for AI processing.
    """
    articles = KnowledgeBaseArticle.objects.all().values(
        'kb_id', 'title', 'content', 'tags', 
        'created_at', 'updated_at', 'helpful_votes', 'total_votes'
    )
    return Response(list(articles))

@api_view(['POST'])
@permission_classes([AllowAny])  # You can add authentication later
def search_kb_for_agent(request):
    """
    Search Knowledge Base articles for FastAPI agent.
    POST body: {"query": "search term", "limit": 10}
    """
    query = request.data.get('query', '')
    limit = request.data.get('limit', 10)
    
    if not query:
        return Response({'error': 'Query parameter is required'}, status=400)
    
    articles = KnowledgeBaseArticle.objects.filter(
        Q(title__icontains=query) |
        Q(content__icontains=query)
    ).order_by('-helpful_votes', '-views')[:limit]
    
    serializer = KnowledgeBaseArticleSerializer(articles, many=True)
    return Response({
        'query': query,
        'results': serializer.data,
        'count': len(serializer.data)
    })

@api_view(['GET'])
@permission_classes([AllowAny])  # You can add authentication later
def kb_article_by_id(request, kb_id):
    """
    Get specific Knowledge Base article by ID for FastAPI agent.
    """
    try:
        article = KnowledgeBaseArticle.objects.get(kb_id=kb_id)
        serializer = KnowledgeBaseArticleSerializer(article)
        return Response(serializer.data)
    except KnowledgeBaseArticle.DoesNotExist:
        return Response({'error': 'Article not found'}, status=404)
