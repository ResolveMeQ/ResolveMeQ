"""
HTTP Caching decorators for API responses
"""
from functools import wraps
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.views.decorators.cache import cache_page
import hashlib
import json


def cache_api_response(max_age=300, public=True, must_revalidate=False):
    """
    Add caching headers to API responses.
    
    Args:
        max_age: Cache duration in seconds (default: 5 minutes)
        public: Whether cache can be shared (default: True)
        must_revalidate: Whether cache must revalidate when stale (default: False)
    
    Usage:
        @cache_api_response(max_age=60)
        @api_view(['GET'])
        def my_view(request):
            return Response({...})
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            
            # Only cache successful GET requests
            if request.method == 'GET' and response.status_code == 200:
                patch_cache_control(
                    response,
                    max_age=max_age,
                    public=public,
                    must_revalidate=must_revalidate
                )
                
                # Add Vary header for content negotiation
                patch_vary_headers(response, ['Accept', 'Authorization'])
                
                # Generate ETag based on response content
                if hasattr(response, 'data'):
                    content = json.dumps(response.data, sort_keys=True).encode('utf-8')
                    etag = hashlib.md5(content).hexdigest()
                    response['ETag'] = f'"{etag}"'
                    
                    # Check If-None-Match header
                    if request.META.get('HTTP_IF_NONE_MATCH') == f'"{etag}"':
                        response.status_code = 304
                        response.content = b''
            
            return response
        return wrapper
    return decorator


def no_cache(view_func):
    """
    Explicitly disable caching for sensitive endpoints.
    
    Usage:
        @no_cache
        @api_view(['POST'])
        def sensitive_view(request):
            return Response({...})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        patch_cache_control(
            response,
            no_cache=True,
            no_store=True,
            must_revalidate=True,
            max_age=0
        )
        return response
    return wrapper
