from .models import KnowledgeBaseArticle, LLMResponse, LLMResponseVote
from tickets.models import Ticket
from django.db import transaction
from django.db.models import Count, Q
import logging

logger = logging.getLogger(__name__)

class KnowledgeBaseService:
    @staticmethod
    def store_llm_response(query, response, response_type, ticket=None, related_kb_articles=None):
        """
        Store an LLM response for future learning and analysis.
        
        Args:
            query (str): The original query
            response (str): The LLM's response
            response_type (str): Type of response (TICKET, KB, GENERAL)
            ticket (Ticket, optional): Related ticket if applicable
            related_kb_articles (list, optional): List of related KB articles
        """
        try:
            with transaction.atomic():
                llm_response = LLMResponse.objects.create(
                    query=query,
                    response=response,
                    response_type=response_type,
                    ticket=ticket
                )
                
                if related_kb_articles:
                    llm_response.related_kb_articles.set(related_kb_articles)
                
                return llm_response
        except Exception as e:
            logger.error(f"Error storing LLM response: {str(e)}")
            raise

    @staticmethod
    def create_kb_article_from_response(llm_response, title=None):
        """
        Create a new KB article from a successful LLM response.
        
        Args:
            llm_response (LLMResponse): The LLM response to convert
            title (str, optional): Custom title for the KB article
        """
        try:
            if llm_response.helpfulness_score < 80:  # Only create KB articles from highly rated responses
                return None
                
            article = KnowledgeBaseArticle.objects.create(
                title=title or f"KB Article from {llm_response.response_type} Response",
                content=llm_response.response,
                tags=[]  # Tags can be added later through admin interface
            )
            
            # Link the KB article back to the LLM response
            llm_response.related_kb_articles.add(article)
            
            return article
        except Exception as e:
            logger.error(f"Error creating KB article from response: {str(e)}")
            raise

    @staticmethod
    def update_response_rating(response_id, is_helpful, user=None):
        """
        Update the helpfulness rating of an LLM response.
        
        Args:
            response_id (UUID): The ID of the LLM response
            is_helpful (bool): Whether the response was helpful
        """
        try:
            response = LLMResponse.objects.get(response_id=response_id)
            if user and getattr(user, "is_authenticated", False):
                LLMResponseVote.objects.update_or_create(
                    response=response,
                    user=user,
                    defaults={"is_helpful": is_helpful},
                )
                agg = response.user_votes.aggregate(
                    total=Count("id"),
                    helpful=Count("id", filter=Q(is_helpful=True)),
                )
                response.total_votes = agg["total"] or 0
                response.helpful_votes = agg["helpful"] or 0
            else:
                response.total_votes += 1
                if is_helpful:
                    response.helpful_votes += 1
            response.save()
            
            # If response becomes highly rated, consider creating a KB article
            if response.helpfulness_score >= 80 and not response.related_kb_articles.exists():
                KnowledgeBaseService.create_kb_article_from_response(response)
                
            return response
        except LLMResponse.DoesNotExist:
            logger.error(f"LLM response not found: {response_id}")
            raise
        except Exception as e:
            logger.error(f"Error updating response rating: {str(e)}")
            raise

    @staticmethod
    def get_related_responses(query, limit=5):
        """
        Get related LLM responses for a given query.
        
        Args:
            query (str): The search query
            limit (int): Maximum number of responses to return
        """
        # This is a simple implementation. In production, you might want to use
        # more sophisticated search algorithms or vector similarity search
        return LLMResponse.objects.filter(
            query__icontains=query
        ).order_by('-helpfulness_score', '-created_at')[:limit] 