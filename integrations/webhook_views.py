from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from tickets.scoping import active_team_id_for_user

from .connectors.webhook import (
    WEBHOOK_EVENTS,
    build_event_payload,
    deliver_webhook_now,
    fan_out_webhook_event,
    generate_secret,
    queue_signed_webhook,
)
from .models import WebhookDelivery, WebhookEndpoint
from .url_safety import UnsafeWebhookURLError, validate_webhook_url
from .webhook_scoping import user_can_edit_webhook, user_can_manage_webhooks, webhooks_queryset_for_user


def _endpoint_to_dict(endpoint: WebhookEndpoint, *, include_secret: bool = False) -> dict:
    data = {
        "id": endpoint.id,
        "name": endpoint.name,
        "url": endpoint.url,
        "events": endpoint.events or [],
        "is_active": endpoint.is_active,
        "failure_count": endpoint.failure_count,
        "circuit_open_until": endpoint.circuit_open_until,
        "team_id": str(endpoint.resolvemeq_team_id),
        "created_at": endpoint.created_at,
        "updated_at": endpoint.updated_at,
    }
    if include_secret:
        data["secret"] = endpoint.secret
    else:
        secret = endpoint.secret or ""
        data["secret_preview"] = f"{secret[:10]}…" if len(secret) > 10 else "—"
    return data


def _delivery_to_dict(delivery: WebhookDelivery) -> dict:
    return {
        "id": delivery.id,
        "delivery_id": str(delivery.delivery_id),
        "endpoint_id": delivery.endpoint_id,
        "event_type": delivery.event_type,
        "url": delivery.url,
        "status": delivery.status,
        "attempts": delivery.attempts,
        "response_code": delivery.response_code,
        "error_message": delivery.error_message,
        "created_at": delivery.created_at,
        "delivered_at": delivery.delivered_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def webhook_metadata(request):
    return Response({
        "events": sorted(WEBHOOK_EVENTS),
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def webhook_list_create(request):
    can_manage = user_can_manage_webhooks(request.user)
    if request.method == "GET":
        qs = webhooks_queryset_for_user(request.user).order_by("-updated_at")
        return Response({
            "can_manage": can_manage,
            "endpoints": [_endpoint_to_dict(e) for e in qs],
        })

    if not can_manage:
        return Response({"error": "Only the workspace owner can manage webhooks."}, status=403)

    url = (request.data.get("url") or "").strip()
    if not url:
        return Response({"error": "url is required."}, status=400)
    try:
        validate_webhook_url(url)
    except UnsafeWebhookURLError as exc:
        return Response({"error": str(exc)}, status=400)

    tid = active_team_id_for_user(request.user)
    team = Team.objects.filter(pk=tid).first() if tid else None
    if not team:
        return Response({"error": "Select an active workspace before creating a webhook."}, status=400)

    events = request.data.get("events") or []
    if events and not isinstance(events, list):
        return Response({"error": "events must be a list."}, status=400)
    invalid = [e for e in events if e not in WEBHOOK_EVENTS]
    if invalid:
        return Response({"error": f"Invalid events: {', '.join(invalid)}"}, status=400)

    endpoint = WebhookEndpoint.objects.create(
        resolvemeq_team=team,
        name=(request.data.get("name") or "").strip()[:120],
        url=url[:512],
        secret=generate_secret(),
        events=events,
        is_active=bool(request.data.get("is_active", True)),
        created_by=request.user,
    )
    return Response({"endpoint": _endpoint_to_dict(endpoint, include_secret=True)}, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def webhook_detail(request, endpoint_id):
    endpoint = WebhookEndpoint.objects.filter(pk=endpoint_id).first()
    if not endpoint or not webhooks_queryset_for_user(request.user).filter(pk=endpoint.pk).exists():
        return Response({"error": "Webhook endpoint not found."}, status=404)

    if request.method == "GET":
        return Response({"endpoint": _endpoint_to_dict(endpoint)})

    if not user_can_edit_webhook(request.user, endpoint):
        return Response({"error": "You do not have permission to edit this webhook."}, status=403)

    if request.method == "DELETE":
        endpoint.delete()
        return Response({"deleted": True})

    updates = {}
    if "name" in request.data:
        updates["name"] = (request.data.get("name") or "").strip()[:120]
    if "url" in request.data:
        url = (request.data.get("url") or "").strip()
        if not url:
            return Response({"error": "url cannot be empty."}, status=400)
        try:
            validate_webhook_url(url)
        except UnsafeWebhookURLError as exc:
            return Response({"error": str(exc)}, status=400)
        updates["url"] = url[:512]
    if "is_active" in request.data:
        updates["is_active"] = bool(request.data.get("is_active"))
    if "events" in request.data:
        events = request.data.get("events") or []
        if not isinstance(events, list):
            return Response({"error": "events must be a list."}, status=400)
        invalid = [e for e in events if e not in WEBHOOK_EVENTS]
        if invalid:
            return Response({"error": f"Invalid events: {', '.join(invalid)}"}, status=400)
        updates["events"] = events
    if "rotate_secret" in request.data and request.data.get("rotate_secret"):
        updates["secret"] = generate_secret()

    if updates:
        for field, value in updates.items():
            setattr(endpoint, field, value)
        endpoint.save(update_fields=list(updates.keys()) + ["updated_at"])

    include_secret = bool(request.data.get("rotate_secret"))
    return Response({"endpoint": _endpoint_to_dict(endpoint, include_secret=include_secret)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook_test(request, endpoint_id):
    endpoint = WebhookEndpoint.objects.filter(pk=endpoint_id).first()
    if not endpoint or not webhooks_queryset_for_user(request.user).filter(pk=endpoint.pk).exists():
        return Response({"error": "Webhook endpoint not found."}, status=404)
    if not user_can_edit_webhook(request.user, endpoint):
        return Response({"error": "You do not have permission to test this webhook."}, status=403)

    event_type = (request.data.get("event_type") or "ticket.created").strip()
    if event_type not in WEBHOOK_EVENTS:
        return Response({"error": "Invalid event_type."}, status=400)

    context = {
        "team_id": str(endpoint.resolvemeq_team_id),
        "category": "onboarding",
        "status": "new",
    }
    ticket_id = request.data.get("ticket_id")
    if ticket_id:
        from tickets.models import Ticket

        ticket = Ticket.objects.filter(pk=ticket_id, team_id=endpoint.resolvemeq_team_id).first()
        if ticket:
            context["ticket"] = ticket
            context["category"] = ticket.category
            context["status"] = ticket.status

    delivery_id = queue_signed_webhook(
        event_type=event_type,
        url=endpoint.url,
        secret=endpoint.secret,
        context=context,
        team_id=str(endpoint.resolvemeq_team_id),
        endpoint=endpoint,
        sync=True,
    )
    delivery = WebhookDelivery.objects.filter(pk=delivery_id).first()
    return Response({
        "delivery": _delivery_to_dict(delivery) if delivery else None,
        "payload": build_event_payload(event_type, context),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def webhook_deliveries(request):
    endpoint_ids = list(webhooks_queryset_for_user(request.user).values_list("pk", flat=True))
    qs = WebhookDelivery.objects.filter(endpoint_id__in=endpoint_ids).select_related("endpoint")[:50]
    return Response({"deliveries": [_delivery_to_dict(d) for d in qs]})
