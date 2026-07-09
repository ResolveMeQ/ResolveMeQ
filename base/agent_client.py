"""Central HTTP client for ResolveMeQ AI agent calls (circuit breaker + SLO)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings

from base.agent_circuit import (
    agent_circuit_is_open,
    record_agent_circuit_skip,
    record_agent_failure,
    record_agent_fallback,
    record_agent_success,
)
from base.agent_http import get_agent_service_headers

logger = logging.getLogger(__name__)


class AgentCallError(Exception):
    def __init__(self, message: str, *, circuit_open: bool = False):
        super().__init__(message)
        self.circuit_open = circuit_open


def agent_http_timeout(requested: Optional[int] = None) -> int:
    default = int(getattr(settings, "AI_AGENT_HTTP_TIMEOUT", 30))
    cap = int(getattr(settings, "AI_AGENT_HTTP_TIMEOUT_MAX", 30))
    timeout = requested if requested is not None else default
    return min(max(int(timeout), 1), cap)


def default_analyze_url() -> str:
    return getattr(settings, "AI_AGENT_URL", "https://agent.resolvemeq.net/tickets/analyze/")


def call_agent_json(
    url: str,
    payload: Dict[str, Any],
    *,
    timeout: Optional[int] = None,
    operation: str = "analyze",
) -> Dict[str, Any]:
    """
    POST JSON to the agent with circuit breaker protection.
    Raises AgentCallError when circuit is open or the HTTP call fails.
    """
    if agent_circuit_is_open():
        record_agent_circuit_skip()
        raise AgentCallError("AI agent circuit is open — using fallback.", circuit_open=True)

    timeout_s = agent_http_timeout(timeout)
    started = time.perf_counter()
    try:
        response = requests.post(
            url,
            json=payload,
            headers=get_agent_service_headers(),
            timeout=timeout_s,
        )
        response.raise_for_status()
        latency_ms = (time.perf_counter() - started) * 1000
        record_agent_success(latency_ms)
        return response.json()
    except (requests.RequestException, OSError) as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        record_agent_failure(latency_ms, str(exc))
        logger.warning("AI agent %s call failed (%s): %s", operation, url, exc)
        raise AgentCallError(str(exc)) from exc


def call_agent_analyze(
    payload: Dict[str, Any],
    *,
    timeout: Optional[int] = None,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    return call_agent_json(url or default_analyze_url(), payload, timeout=timeout, operation="analyze")


def build_ticket_analyze_fallback(ticket, *, reason: str = "") -> Dict[str, Any]:
    """Placeholder analyze response when agent is unavailable."""
    record_agent_fallback()
    category = getattr(ticket, "category", None) or "general"
    return {
        "confidence": 0.0,
        "recommended_action": "request_clarification",
        "analysis": {
            "category": category,
            "severity": "medium",
            "complexity": "medium",
        },
        "solution": {
            "steps": [
                "The AI assistant is temporarily unavailable.",
                "A support agent will review this ticket shortly.",
                "You can add more details in the ticket chat while you wait.",
            ],
            "estimated_time": "Pending agent availability",
            "success_probability": 0.0,
        },
        "reasoning": reason or "AI agent service is temporarily unavailable.",
        "agent_fallback": True,
        "fallback_used": True,
    }


def try_call_agent_analyze(
    payload: Dict[str, Any],
    *,
    ticket=None,
    timeout: Optional[int] = None,
    url: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns (agent_json, error_message). Never raises."""
    try:
        return call_agent_analyze(payload, timeout=timeout, url=url), None
    except AgentCallError as exc:
        if ticket is not None:
            return build_ticket_analyze_fallback(ticket, reason=str(exc)), str(exc)
        return None, str(exc)
