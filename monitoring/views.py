from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django.conf import settings
from django.db import connection
from django.core.cache import cache
import requests
from celery import current_app
from datetime import datetime


def build_service_health_results() -> dict:
    """
    Database, Redis/cache, Celery (inspect + health_ping round-trip), AI agent, and email dispatch mode.
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.DEBUG and "development" or "production",
        "services": {},
    }

    # Test Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        results["services"]["database"] = {
            "status": "healthy",
            "engine": settings.DATABASES["default"]["ENGINE"],
            "host": settings.DATABASES["default"]["HOST"],
        }
    except Exception as e:
        results["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Test Redis (via Django cache)
    try:
        redis_url = settings.REDIS_URL
        cache_test_key = "_health_check_test"
        cache.set(cache_test_key, "OK", 10)
        cache_result = cache.get(cache_test_key)

        results["services"]["redis"] = {
            "status": "healthy" if cache_result == "OK" else "degraded",
            "url": redis_url.split("@")[-1] if "@" in redis_url else redis_url.split("//")[1],
        }
    except Exception as e:
        results["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Test Celery: broker + inspect + task round-trip
    try:
        celery_app = current_app
        inspector = celery_app.control.inspect(timeout=3.0)
        active_workers = inspector.active()
        stats = inspector.stats()

        broker_hint = (
            settings.CELERY_BROKER_URL.split("@")[-1]
            if "@" in settings.CELERY_BROKER_URL
            else settings.CELERY_BROKER_URL.replace("redis://", "").replace("rediss://", "")
        )

        celery_info = {
            "broker_url": broker_hint,
            "inspect_workers_seen": active_workers is not None,
            "worker_count": len(active_workers.keys()) if active_workers else 0,
            "worker_names": list(active_workers.keys()) if active_workers else [],
        }
        if stats:
            celery_info["worker_stats_keys"] = list(stats.keys())

        task_ping = {"status": "unknown"}
        try:
            from base.tasks import health_ping

            async_result = health_ping.apply_async()
            ping_payload = async_result.get(timeout=8.0)
            task_ping = {
                "status": "healthy",
                "response": ping_payload,
            }
        except Exception as ping_exc:
            task_ping = {
                "status": "unhealthy",
                "error": str(ping_exc),
                "hint": "Workers may be down, not consuming this queue, or broker URL mismatch between web and worker.",
            }

        if task_ping.get("status") == "healthy":
            celery_info["status"] = "healthy"
        elif active_workers is not None:
            celery_info["status"] = "degraded"
            celery_info["message"] = (
                "Inspect sees workers but task ping failed — check worker logs and CELERY_BROKER_URL."
            )
        else:
            celery_info["status"] = "unhealthy"
            celery_info["message"] = "No workers responding to inspect and task ping failed."

        celery_info["task_ping"] = task_ping
        results["services"]["celery"] = celery_info
    except Exception as e:
        results["services"]["celery"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Test AI Agent
    try:
        agent_url = getattr(settings, "AI_AGENT_URL", "").replace("/tickets/analyze/", "/health")

        if agent_url and agent_url != "/health":
            response = requests.get(agent_url, timeout=5)
            if response.status_code == 200:
                agent_data = response.json()
                results["services"]["agent"] = {
                    "status": "healthy",
                    "url": agent_url,
                    "version": agent_data.get("version", "unknown"),
                    "agent_status": agent_data.get("status", "unknown"),
                }
            else:
                results["services"]["agent"] = {
                    "status": "degraded",
                    "url": agent_url,
                    "http_status": response.status_code,
                }
        else:
            results["services"]["agent"] = {
                "status": "not_configured",
                "message": "AI_AGENT_URL not set",
            }
    except Exception as e:
        results["services"]["agent"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # All transactional templates go through dispatch_send_email_with_template — one mode for the app
    try:
        from base.tasks import email_dispatch_uses_celery

        results["email_outbound"] = {
            "delivery": "celery_queued" if email_dispatch_uses_celery() else "synchronous_in_web_process",
            "hint": "Set EMAIL_USE_CELERY=true in production so SMTP runs on workers; unset defaults to sync when using runserver.",
        }
    except Exception as e:
        results["email_outbound"] = {"delivery": "unknown", "error": str(e)}

    all_healthy = all(
        service.get("status") == "healthy"
        for service in results["services"].values()
        if service.get("status") != "not_configured"
    )

    results["overall_status"] = "healthy" if all_healthy else "degraded"

    return results


@api_view(["GET"])
@permission_classes([IsAdminUser])
def service_health_check(request):
    """
    Comprehensive service health check (admin JWT required).
    Tests: Database, Redis, Celery (including task round-trip), AI agent, email dispatch mode.
    """
    return Response(build_service_health_results())


@api_view(["GET"])
@permission_classes([AllowAny])
def service_health_complete(request):
    """
    Same payload as /health/services/, authenticated with MONITORING_HEALTH_SECRET.
    Use for uptime monitors when admin JWT is not practical.

    GET /api/monitoring/health/complete/?token=SECRET
    or header: X-Monitoring-Token: SECRET

    Returns 404 if secret is not configured or token is wrong (avoid leaking existence).
    """
    expected = getattr(settings, "MONITORING_HEALTH_SECRET", "").strip()
    if not expected:
        return Response({"detail": "Not found."}, status=404)
    token = (request.GET.get("token") or request.headers.get("X-Monitoring-Token") or "").strip()
    if token != expected:
        return Response({"detail": "Not found."}, status=404)
    return Response(build_service_health_results())


@api_view(["GET"])
def basic_health_check(request):
    """
    Basic health check endpoint (public, no auth required).
    Returns 200 OK if Django is running.
    """
    return Response({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    })
