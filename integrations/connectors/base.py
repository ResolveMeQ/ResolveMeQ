"""Shared connector utilities: timeouts, retries, circuit breaker."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10
MAX_FAILURES_BEFORE_OPEN = 5
CIRCUIT_OPEN_MINUTES = 5


class ConnectorError(Exception):
    """Raised when an outbound connector call fails."""


def http_post_json(
    url: str,
    *,
    body: bytes,
    headers: dict,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> requests.Response:
    try:
        return requests.post(url, data=body, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise ConnectorError(str(exc)) from exc


def http_get_json(
    url: str,
    *,
    headers: dict,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> requests.Response:
    try:
        return requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise ConnectorError(str(exc)) from exc


def circuit_is_open(endpoint) -> bool:
    until = getattr(endpoint, "circuit_open_until", None)
    return bool(until and until > timezone.now())


def record_delivery_success(endpoint) -> None:
    if not endpoint:
        return
    endpoint.failure_count = 0
    endpoint.circuit_open_until = None
    endpoint.save(update_fields=["failure_count", "circuit_open_until", "updated_at"])


def record_delivery_failure(endpoint) -> None:
    if not endpoint:
        return
    endpoint.failure_count = (endpoint.failure_count or 0) + 1
    if endpoint.failure_count >= MAX_FAILURES_BEFORE_OPEN:
        endpoint.circuit_open_until = timezone.now() + timedelta(minutes=CIRCUIT_OPEN_MINUTES)
        logger.warning(
            "Webhook endpoint %s circuit opened until %s",
            endpoint.pk,
            endpoint.circuit_open_until,
        )
    endpoint.save(update_fields=["failure_count", "circuit_open_until", "updated_at"])


def should_retry(status_code: Optional[int]) -> bool:
    if status_code is None:
        return True
    if status_code >= 500:
        return True
    if status_code == 429:
        return True
    return False
