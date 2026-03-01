from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.conf import settings
from django.db import connection
from django.core.cache import cache
import redis
import requests
from celery import current_app
from datetime import datetime


@api_view(['GET'])
@permission_classes([IsAdminUser])
def service_health_check(request):
    """
    Comprehensive service health check endpoint.
    Tests: Database, Redis, Celery, AI Agent
    
    Restricted to admin users only.
    """
    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'environment': settings.DEBUG and 'development' or 'production',
        'services': {}
    }
    
    # Test Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        results['services']['database'] = {
            'status': 'healthy',
            'engine': settings.DATABASES['default']['ENGINE'],
            'host': settings.DATABASES['default']['HOST']
        }
    except Exception as e:
        results['services']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Test Redis
    try:
        redis_url = settings.REDIS_URL
        cache_test_key = '_health_check_test'
        cache.set(cache_test_key, 'OK', 10)
        cache_result = cache.get(cache_test_key)
        
        results['services']['redis'] = {
            'status': 'healthy' if cache_result == 'OK' else 'degraded',
            'url': redis_url.split('@')[-1] if '@' in redis_url else redis_url.split('//')[1]
        }
    except Exception as e:
        results['services']['redis'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Test Celery
    try:
        celery_app = current_app
        inspector = celery_app.control.inspect(timeout=3.0)
        active_workers = inspector.active()
        stats = inspector.stats()
        
        if active_workers is not None:
            worker_count = len(active_workers.keys())
            results['services']['celery'] = {
                'status': 'healthy',
                'workers': worker_count,
                'worker_names': list(active_workers.keys()) if worker_count > 0 else [],
                'broker_url': settings.CELERY_BROKER_URL.split('@')[-1] if '@' in settings.CELERY_BROKER_URL else 'local'
            }
        else:
            results['services']['celery'] = {
                'status': 'degraded',
                'message': 'No workers responding',
                'broker_url': settings.CELERY_BROKER_URL.split('@')[-1] if '@' in settings.CELERY_BROKER_URL else 'local'
            }
    except Exception as e:
        results['services']['celery'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Test AI Agent
    try:
        agent_url = getattr(settings, 'AI_AGENT_URL', '').replace('/tickets/analyze/', '/health')
        
        if agent_url and agent_url != '/health':
            response = requests.get(agent_url, timeout=5)
            if response.status_code == 200:
                agent_data = response.json()
                results['services']['agent'] = {
                    'status': 'healthy',
                    'url': agent_url,
                    'version': agent_data.get('version', 'unknown'),
                    'agent_status': agent_data.get('status', 'unknown')
                }
            else:
                results['services']['agent'] = {
                    'status': 'degraded',
                    'url': agent_url,
                    'http_status': response.status_code
                }
        else:
            results['services']['agent'] = {
                'status': 'not_configured',
                'message': 'AI_AGENT_URL not set'
            }
    except Exception as e:
        results['services']['agent'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Overall health status
    all_healthy = all(
        service.get('status') == 'healthy' 
        for service in results['services'].values()
        if service.get('status') != 'not_configured'
    )
    
    results['overall_status'] = 'healthy' if all_healthy else 'degraded'
    
    return Response(results)


@api_view(['GET'])
def basic_health_check(request):
    """
    Basic health check endpoint (public, no auth required).
    Returns 200 OK if Django is running.
    """
    return Response({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat()
    })
