"""Shared HTTP headers for outbound calls to the ResolveMeQ FastAPI agent."""
from django.conf import settings


def get_agent_service_headers(extra=None):
    """
    Headers for POSTs to AI_AGENT_URL. When AI_AGENT_SERVICE_KEY is set, sends X-API-Key
    so the agent can reject unsigned traffic.
    """
    headers = {'Content-Type': 'application/json'}
    key = (getattr(settings, 'AI_AGENT_SERVICE_KEY', None) or '').strip()
    if key:
        headers['X-API-Key'] = key
    if extra:
        headers.update(extra)
    return headers
