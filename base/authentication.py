from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import os


class CookiesJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get('access_token')

        if not access_token:
            return None
        
        validated_token = self.get_validated_token(access_token)

        try:
            user = self.get_user(validated_token)
        except AuthenticationFailed:
            return None

        return (user, validated_token)


class AgentAPIKeyAuthentication(BaseAuthentication):
    """
    Authentication class for AI Agent using API Key.
    The agent sends X-Agent-API-Key header with requests.
    """
    
    def authenticate(self, request):
        # Get the API key from request headers
        api_key = request.headers.get('X-Agent-API-Key') or request.META.get('HTTP_X_AGENT_API_KEY')
        
        if not api_key:
            return None  # No authentication attempted
        
        # Get expected API key from environment or settings
        expected_key = getattr(settings, 'AGENT_API_KEY', os.getenv('AGENT_API_KEY', 'resolvemeq-agent-secret-key-2026'))
        
        if api_key != expected_key:
            raise AuthenticationFailed('Invalid Agent API Key')
        
        # Return a tuple of (user, auth) - we'll use None for user since it's the agent
        # This allows the view to know it's authenticated but not tied to a specific user
        return (None, api_key)
    
    def authenticate_header(self, request):
        return 'X-Agent-API-Key'