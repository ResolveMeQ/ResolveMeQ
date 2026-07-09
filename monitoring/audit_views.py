import csv
import json
from datetime import datetime
from io import StringIO

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from monitoring.audit import audit_from_request
from monitoring.audit_scoping import audit_queryset_for_user, user_can_view_audit
from monitoring.models import ComplianceAuditEvent
from tickets.scoping import active_team_id_for_user


def _event_to_dict(event: ComplianceAuditEvent) -> dict:
    return {
        "id": str(event.id),
        "team_id": str(event.team_id) if event.team_id else None,
        "actor_email": event.actor_email,
        "event_type": event.event_type,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "summary": event.summary,
        "metadata": event.metadata or {},
        "ip_address": event.ip_address,
        "created_at": event.created_at,
    }


def _parse_since_until(request):
    since = request.GET.get("since")
    until = request.GET.get("until")
    since_dt = parse_datetime(since) if since else None
    until_dt = parse_datetime(until) if until else None
    return since_dt, until_dt


def _filtered_events(request):
    qs = audit_queryset_for_user(request.user)
    event_type = (request.GET.get("event_type") or "").strip()
    if event_type:
        qs = qs.filter(event_type=event_type)
    since_dt, until_dt = _parse_since_until(request)
    if since_dt:
        qs = qs.filter(created_at__gte=since_dt)
    if until_dt:
        qs = qs.filter(created_at__lte=until_dt)
    return qs.select_related("team", "actor")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_events(request):
    """List compliance audit events for the active workspace (team owner or staff)."""
    if not user_can_view_audit(request.user):
        return Response({"error": "Only the workspace owner can view the compliance audit log."}, status=403)

    limit = min(int(request.GET.get("limit", 50)), 200)
    offset = max(int(request.GET.get("offset", 0)), 0)
    qs = _filtered_events(request)
    total = qs.count()
    events = qs[offset : offset + limit]
    return Response({
        "team_id": active_team_id_for_user(request.user),
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [_event_to_dict(e) for e in events],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_export(request):
    """Export compliance audit events as CSV or JSON."""
    if not user_can_view_audit(request.user):
        return Response({"error": "Only the workspace owner can export the compliance audit log."}, status=403)

    export_fmt = (request.GET.get("export_format") or request.GET.get("format") or "csv").lower()
    qs = _filtered_events(request).order_by("created_at")
    events = list(qs[:10000])

    tid = active_team_id_for_user(request.user)
    team = Team.objects.filter(pk=tid).first() if tid else None
    audit_from_request(
        request,
        event_type="audit.exported",
        team=team,
        summary=f"Exported {len(events)} compliance audit events as {export_fmt}",
        resource_type="audit_log",
        metadata={"format": export_fmt, "count": len(events)},
    )

    if export_fmt == "json":
        payload = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "count": len(events),
            "events": [_event_to_dict(e) for e in events],
        }
        response = HttpResponse(
            json.dumps(payload, indent=2, default=str),
            content_type="application/json",
        )
        response["Content-Disposition"] = 'attachment; filename="resolvemeq-audit-export.json"'
        return response

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "created_at",
        "event_type",
        "actor_email",
        "resource_type",
        "resource_id",
        "summary",
        "metadata",
        "ip_address",
        "team_id",
    ])
    for event in events:
        writer.writerow([
            event.created_at.isoformat(),
            event.event_type,
            event.actor_email,
            event.resource_type,
            event.resource_id,
            event.summary,
            json.dumps(event.metadata or {}),
            event.ip_address or "",
            str(event.team_id) if event.team_id else "",
        ])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="resolvemeq-audit-export.csv"'
    return response
