"""Record append-only compliance audit events."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def get_client_ip(request) -> Optional[str]:
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit_event(
    *,
    event_type: str,
    summary: str,
    team=None,
    actor=None,
    resource_type: str = "",
    resource_id: str = "",
    metadata: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Best-effort audit write — never raises to callers."""
    try:
        from monitoring.models import ComplianceAuditEvent

        actor_email = ""
        if actor is not None:
            actor_email = getattr(actor, "email", "") or ""

        ComplianceAuditEvent.objects.create(
            team=team,
            actor=actor,
            actor_email=actor_email[:255],
            event_type=event_type,
            resource_type=(resource_type or "")[:64],
            resource_id=str(resource_id or "")[:128],
            summary=summary[:4000],
            metadata=metadata or {},
            ip_address=ip_address,
        )
    except Exception as exc:
        logger.warning("Failed to record compliance audit event (%s): %s", event_type, exc)


def audit_from_request(request, **kwargs: Any) -> None:
    actor = getattr(request, "user", None)
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    record_audit_event(actor=actor, ip_address=get_client_ip(request), **kwargs)
