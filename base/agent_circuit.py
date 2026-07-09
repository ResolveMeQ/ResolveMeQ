"""Circuit breaker and SLO metrics for outbound AI agent HTTP calls."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CACHE_FAILURES = "agent_circuit:failures"
CACHE_OPEN_UNTIL = "agent_circuit:open_until"
CACHE_METRICS = "agent_circuit:metrics"


def _max_failures() -> int:
    return int(getattr(settings, "AI_AGENT_CIRCUIT_MAX_FAILURES", 5))


def _open_seconds() -> int:
    return int(getattr(settings, "AI_AGENT_CIRCUIT_OPEN_SECONDS", 300))


def agent_circuit_is_open() -> bool:
    open_until_ts = cache.get(CACHE_OPEN_UNTIL)
    if not open_until_ts:
        return False
    now_ts = timezone.now().timestamp()
    if open_until_ts > now_ts:
        return True
    cache.delete(CACHE_OPEN_UNTIL)
    cache.set(CACHE_FAILURES, 0, timeout=3600)
    return False


def agent_circuit_open_until() -> Optional[datetime]:
    open_until_ts = cache.get(CACHE_OPEN_UNTIL)
    if not open_until_ts:
        return None
    return datetime.fromtimestamp(open_until_ts, tz=dt_timezone.utc)


def _load_metrics() -> Dict[str, Any]:
    data = cache.get(CACHE_METRICS)
    if not isinstance(data, dict):
        return {
            "calls_total": 0,
            "success_total": 0,
            "failure_total": 0,
            "circuit_open_total": 0,
            "fallback_total": 0,
            "latency_ms_sum": 0.0,
            "latency_ms_max": 0.0,
            "last_success_at": None,
            "last_failure_at": None,
        }
    return data


def _save_metrics(data: Dict[str, Any]) -> None:
    cache.set(CACHE_METRICS, data, timeout=86400 * 7)


def _record_metric(event: str, latency_ms: float = 0.0) -> None:
    metrics = _load_metrics()
    metrics["calls_total"] = int(metrics.get("calls_total", 0)) + 1
    if event == "success":
        metrics["success_total"] = int(metrics.get("success_total", 0)) + 1
        metrics["last_success_at"] = timezone.now().isoformat()
    elif event == "failure":
        metrics["failure_total"] = int(metrics.get("failure_total", 0)) + 1
        metrics["last_failure_at"] = timezone.now().isoformat()
    elif event == "circuit_open":
        metrics["circuit_open_total"] = int(metrics.get("circuit_open_total", 0)) + 1
    elif event == "fallback":
        metrics["fallback_total"] = int(metrics.get("fallback_total", 0)) + 1
    if latency_ms > 0:
        metrics["latency_ms_sum"] = float(metrics.get("latency_ms_sum", 0.0)) + latency_ms
        metrics["latency_ms_max"] = max(float(metrics.get("latency_ms_max", 0.0)), latency_ms)
    _save_metrics(metrics)


def record_agent_success(latency_ms: float) -> None:
    cache.set(CACHE_FAILURES, 0, timeout=3600)
    cache.delete(CACHE_OPEN_UNTIL)
    _record_metric("success", latency_ms=latency_ms)


def record_agent_failure(latency_ms: float, error: str = "") -> None:
    failures = int(cache.get(CACHE_FAILURES) or 0) + 1
    cache.set(CACHE_FAILURES, failures, timeout=3600)
    if failures >= _max_failures():
        open_until = timezone.now().timestamp() + _open_seconds()
        cache.set(CACHE_OPEN_UNTIL, open_until, timeout=_open_seconds() + 120)
        logger.warning(
            "AI agent circuit opened for %ss after %s failures (last error: %s)",
            _open_seconds(),
            failures,
            error[:200],
        )
    _record_metric("failure", latency_ms=latency_ms)


def record_agent_circuit_skip() -> None:
    _record_metric("circuit_open")


def record_agent_fallback() -> None:
    _record_metric("fallback")


def get_agent_slo_status() -> Dict[str, Any]:
    metrics = _load_metrics()
    calls = int(metrics.get("calls_total", 0))
    success = int(metrics.get("success_total", 0))
    latency_sum = float(metrics.get("latency_ms_sum", 0.0))
    open_until = agent_circuit_open_until()
    return {
        "circuit_open": agent_circuit_is_open(),
        "circuit_open_until": open_until.isoformat() if open_until else None,
        "failure_count": int(cache.get(CACHE_FAILURES) or 0),
        "max_failures_before_open": _max_failures(),
        "http_timeout_seconds": int(getattr(settings, "AI_AGENT_HTTP_TIMEOUT", 30)),
        "metrics": {
            **metrics,
            "success_rate": round(success / calls, 4) if calls else None,
            "latency_ms_avg": round(latency_sum / success, 2) if success else None,
        },
    }


def reset_agent_circuit_for_tests() -> None:
    cache.delete(CACHE_FAILURES)
    cache.delete(CACHE_OPEN_UNTIL)
    cache.delete(CACHE_METRICS)
