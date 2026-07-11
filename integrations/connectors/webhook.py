"""HMAC-signed outbound webhook delivery."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional

from django.utils import timezone

from integrations.connectors.base import (
    ConnectorError,
    circuit_is_open,
    http_post_json,
    record_delivery_failure,
    record_delivery_success,
    should_retry,
)
from integrations.url_safety import UnsafeWebhookURLError, validate_webhook_url

logger = logging.getLogger(__name__)

WEBHOOK_EVENTS = frozenset({
    "ticket.created",
    "ticket.escalated",
    "ticket.resolved",
    "workflow.step.completed",
})

SIGNATURE_HEADER = "X-ResolveMeq-Signature"
TIMESTAMP_HEADER = "X-ResolveMeq-Timestamp"
EVENT_HEADER = "X-ResolveMeq-Event"
DELIVERY_HEADER = "X-ResolveMeq-Delivery"


def generate_secret() -> str:
    return f"whsec_{secrets.token_hex(24)}"


def sign_payload(secret: str, body: bytes, timestamp: Optional[int] = None) -> tuple[str, int]:
    ts = timestamp or int(time.time())
    signed_content = f"{ts}.{body.decode('utf-8')}"
    digest = hmac.new(secret.encode(), signed_content.encode(), hashlib.sha256).hexdigest()
    return f"v1={digest}", ts


def verify_signature(secret: str, body: bytes, timestamp: str, signature: str, *, max_age_seconds: int = 300) -> bool:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - ts) > max_age_seconds:
        return False
    expected, _ = sign_payload(secret, body, ts)
    provided = (signature or "").strip()
    if not provided.startswith("v1="):
        return False
    return hmac.compare_digest(expected, provided)


def build_event_payload(event_type: str, context: Dict[str, Any]) -> dict:
    ticket = context.get("ticket")
    workflow = context.get("workflow")
    step = context.get("step")
    team_id = context.get("team_id")
    payload: Dict[str, Any] = {
        "event": event_type,
        "timestamp": timezone.now().isoformat(),
        "team_id": str(team_id) if team_id else None,
    }
    if ticket:
        payload["ticket"] = {
            "ticket_id": ticket.ticket_id,
            "category": ticket.category,
            "status": ticket.status,
            "issue_type": getattr(ticket, "issue_type", None),
        }
    if workflow:
        payload["workflow"] = {
            "workflow_id": str(workflow.id),
            "status": workflow.status,
            "template_name": workflow.template.name if workflow.template_id else None,
        }
    if step:
        payload["step"] = {
            "step_id": step.id,
            "title": step.title,
            "status": step.status,
        }
    return payload


def _endpoint_matches_event(endpoint, event_type: str) -> bool:
    events = endpoint.events or []
    if not events:
        return True
    return event_type in events


def create_delivery(
    *,
    event_type: str,
    payload: dict,
    url: str,
    secret: str,
    team_id: Optional[str] = None,
    endpoint=None,
) -> "WebhookDelivery":
    from integrations.models import WebhookDelivery

    return WebhookDelivery.objects.create(
        delivery_id=uuid.uuid4(),
        endpoint=endpoint,
        event_type=event_type,
        team_id=team_id,
        url=url,
        secret=secret,
        payload=payload,
        status="pending",
    )


def deliver_webhook_now(delivery_id) -> bool:
    from integrations.models import WebhookDelivery

    delivery = (
        WebhookDelivery.objects.select_related("endpoint")
        .filter(pk=delivery_id)
        .first()
    )
    if not delivery:
        return False
    if delivery.status == "success":
        return True

    endpoint = delivery.endpoint
    if endpoint and (not endpoint.is_active or circuit_is_open(endpoint)):
        delivery.status = "failed"
        delivery.error_message = "Endpoint inactive or circuit open."
        delivery.attempts = (delivery.attempts or 0) + 1
        delivery.save(update_fields=["status", "error_message", "attempts", "updated_at"])
        return False

    # Re-validate right before connecting: DNS can change between webhook
    # registration and delivery time (DNS rebinding), so the create/update
    # time check alone isn't enough to prevent SSRF.
    try:
        validate_webhook_url(delivery.url)
    except UnsafeWebhookURLError as exc:
        logger.warning(
            "Blocked webhook delivery %s to unsafe URL: %s", delivery.pk, exc
        )
        delivery.status = "failed"
        delivery.error_message = f"Blocked unsafe webhook URL: {exc}"[:500]
        delivery.attempts = (delivery.attempts or 0) + 1
        delivery.save(update_fields=["status", "error_message", "attempts", "updated_at"])
        record_delivery_failure(endpoint)
        return False

    body = json.dumps(delivery.payload, separators=(",", ":"), default=str).encode("utf-8")
    signature, ts = sign_payload(delivery.secret, body)
    headers = {
        "Content-Type": "application/json",
        EVENT_HEADER: delivery.event_type,
        TIMESTAMP_HEADER: str(ts),
        SIGNATURE_HEADER: signature,
        DELIVERY_HEADER: str(delivery.delivery_id),
    }

    delivery.attempts = (delivery.attempts or 0) + 1
    try:
        response = http_post_json(delivery.url, body=body, headers=headers)
        delivery.response_code = response.status_code
        delivery.response_body = (response.text or "")[:2000]
        if 200 <= response.status_code < 300:
            delivery.status = "success"
            delivery.delivered_at = timezone.now()
            delivery.error_message = ""
            delivery.save()
            record_delivery_success(endpoint)
            return True
        delivery.status = "failed"
        delivery.error_message = f"HTTP {response.status_code}"
        delivery.save()
        record_delivery_failure(endpoint)
        return False
    except ConnectorError as exc:
        delivery.status = "failed"
        delivery.error_message = str(exc)[:500]
        delivery.save()
        record_delivery_failure(endpoint)
        return False


def enqueue_webhook_delivery(delivery_id) -> None:
    try:
        from integrations.tasks import deliver_webhook_task

        deliver_webhook_task.delay(delivery_id)
    except Exception:
        deliver_webhook_now(delivery_id)


def queue_signed_webhook(
    *,
    event_type: str,
    url: str,
    secret: str,
    context: Dict[str, Any],
    team_id: Optional[str] = None,
    endpoint=None,
    sync: bool = False,
) -> int:
    payload = build_event_payload(event_type, context)
    delivery = create_delivery(
        event_type=event_type,
        payload=payload,
        url=url,
        secret=secret or generate_secret(),
        team_id=team_id,
        endpoint=endpoint,
    )
    if sync:
        deliver_webhook_now(delivery.pk)
    else:
        enqueue_webhook_delivery(delivery.pk)
    return delivery.pk


def fan_out_webhook_event(event_type: str, context: Dict[str, Any]) -> List[int]:
    from integrations.models import WebhookEndpoint

    if event_type not in WEBHOOK_EVENTS:
        return []

    team_id = context.get("team_id")
    if team_id:
        team_id = str(team_id)

    qs = WebhookEndpoint.objects.filter(is_active=True)
    if team_id:
        qs = qs.filter(resolvemeq_team_id=team_id)
    else:
        return []

    delivery_ids = []
    for endpoint in qs:
        if not _endpoint_matches_event(endpoint, event_type):
            continue
        if circuit_is_open(endpoint):
            logger.info("Skipping webhook endpoint %s (circuit open)", endpoint.pk)
            continue
        delivery_ids.append(
            queue_signed_webhook(
                event_type=event_type,
                url=endpoint.url,
                secret=endpoint.secret,
                context=context,
                team_id=team_id,
                endpoint=endpoint,
            )
        )
    return delivery_ids


def deliver_ad_hoc_webhook(
    *,
    url: str,
    secret: str,
    event_type: str,
    context: Dict[str, Any],
    dry_run: bool = False,
) -> tuple[bool, str]:
    if dry_run:
        payload = build_event_payload(event_type, context)
        return True, f"Would POST {event_type} to {url} ({len(json.dumps(payload))} bytes)."
    team_id = context.get("team_id")
    delivery_id = queue_signed_webhook(
        event_type=event_type or "automation.webhook",
        url=url,
        secret=secret or generate_secret(),
        context=context,
        team_id=str(team_id) if team_id else None,
        sync=True,
    )
    from integrations.models import WebhookDelivery

    delivery = WebhookDelivery.objects.filter(pk=delivery_id).first()
    if delivery and delivery.status == "success":
        return True, f"Webhook delivered (HTTP {delivery.response_code})."
    msg = delivery.error_message if delivery else "Delivery failed."
    return False, msg
