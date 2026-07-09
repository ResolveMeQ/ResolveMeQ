"""Partner-facing REST API (v1)."""

from __future__ import annotations

import secrets

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from automation.models import Rule
from base.models import User
from integrations.connectors.webhook import WEBHOOK_EVENTS
from public_api.authentication import PartnerAPIKeyAuthentication, PartnerPrincipal
from public_api.permissions import (
    PartnerAuthenticated,
    PartnerRulesRead,
    PartnerTicketsRead,
    PartnerTicketsWrite,
    PartnerWorkflowsRead,
)
from tickets.models import Ticket
from tickets.serializers import TicketSerializer
from tickets.services import compose_issue_type, create_ticket_with_reporter
from workflows.models import Workflow, WorkflowTemplate
from workflows.services import start_workflow


def _team(principal: PartnerPrincipal):
    return principal.team


def _ticket_to_public(ticket: Ticket) -> dict:
    data = TicketSerializer(ticket).data
    return {
        "id": ticket.ticket_id,
        "issue_type": data.get("issue_type"),
        "description": data.get("description"),
        "category": data.get("category"),
        "status": data.get("status"),
        "tags": data.get("tags") or [],
        "assigned_to": data.get("assigned_to"),
        "assigned_to_name": data.get("assigned_to_name"),
        "team_id": str(ticket.team_id) if ticket.team_id else None,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "escalation_priority": ticket.escalation_priority,
        "escalated_at": ticket.escalated_at,
    }


def _workflow_to_public(workflow: Workflow) -> dict:
    steps = []
    for step in workflow.steps.order_by("order_index"):
        steps.append({
            "id": step.id,
            "order_index": step.order_index,
            "title": step.title,
            "status": step.status,
            "step_type": step.step_type,
            "due_at": step.due_at,
            "completed_at": step.completed_at,
        })
    return {
        "id": str(workflow.id),
        "name": workflow.template.name if workflow.template_id else "Workflow",
        "status": workflow.status,
        "ticket_id": workflow.ticket_id,
        "team_id": str(workflow.team_id) if workflow.team_id else None,
        "due_at": workflow.due_at,
        "created_at": workflow.created_at,
        "steps": steps,
    }


def _rule_to_public(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "trigger": rule.trigger,
        "is_active": rule.is_active,
        "team_id": str(rule.team_id) if rule.team_id else None,
        "is_global": rule.team_id is None,
        "priority": rule.priority,
    }


@api_view(["GET"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerAuthenticated])
def public_api_info(request):
    """API capabilities and authenticated key metadata."""
    principal: PartnerPrincipal = request.user
    key = principal.api_key
    return Response({
        "api": "ResolveMeQ Public API",
        "version": "v1",
        "team_id": str(principal.team.id),
        "team_name": principal.team.name,
        "key_name": key.name,
        "scopes": key.scopes or [],
        "webhook_events": sorted(WEBHOOK_EVENTS),
        "docs": "/docs/PUBLIC_API.md",
    })


@api_view(["GET"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerTicketsRead])
def public_ticket_list(request):
    team = _team(request.user)
    limit = min(int(request.GET.get("limit", 50)), 100)
    offset = max(int(request.GET.get("offset", 0)), 0)
    qs = Ticket.objects.filter(team=team).select_related("assigned_to", "user").order_by("-created_at")
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    total = qs.count()
    tickets = [_ticket_to_public(t) for t in qs[offset : offset + limit]]
    return Response({"total": total, "limit": limit, "offset": offset, "tickets": tickets})


@api_view(["GET"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerTicketsRead])
def public_ticket_detail(request, ticket_id):
    team = _team(request.user)
    ticket = get_object_or_404(Ticket.objects.select_related("assigned_to", "user"), ticket_id=ticket_id, team=team)
    return Response({"ticket": _ticket_to_public(ticket)})


@api_view(["POST"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerTicketsWrite])
def public_ticket_create(request):
    team = _team(request.user)
    reporter_email = (request.data.get("reporter_email") or "").strip().lower()
    if not reporter_email:
        return Response({"error": "reporter_email is required."}, status=400)
    issue_type = (request.data.get("issue_type") or request.data.get("subject") or "").strip()
    if not issue_type:
        return Response({"error": "issue_type is required."}, status=400)
    description = (request.data.get("description") or "").strip()
    category = (request.data.get("category") or "other").strip()
    urgency = (request.data.get("urgency") or "").strip().lower() or None
    tags = request.data.get("tags") or []
    if not isinstance(tags, list):
        return Response({"error": "tags must be a list."}, status=400)

    reporter = User.objects.filter(email__iexact=reporter_email).first()
    if not reporter:
        username_base = reporter_email.split("@")[0][:40] or "partner_user"
        reporter = User.objects.create_user(
            username=f"{username_base}_{secrets.token_hex(3)}",
            email=reporter_email,
            password=get_random_string(24),
        )
        team.members.add(reporter)

    ticket = create_ticket_with_reporter(
        reporter,
        team,
        issue_type=compose_issue_type(issue_type, urgency),
        description=description,
        category=category,
        tags=tags,
    )
    return Response({"ticket": _ticket_to_public(ticket)}, status=201)


@api_view(["PATCH"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerTicketsWrite])
def public_ticket_update(request, ticket_id):
    team = _team(request.user)
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id, team=team)
    status_value = (request.data.get("status") or "").strip()
    if not status_value:
        return Response({"error": "status is required."}, status=400)
    allowed = {"new", "open", "in_progress", "pending", "resolved", "closed", "escalated"}
    if status_value not in allowed:
        return Response({"error": f"status must be one of: {', '.join(sorted(allowed))}"}, status=400)
    ticket.status = status_value
    ticket.save(update_fields=["status", "updated_at"])
    if status_value == "resolved":
        try:
            from automation.hooks import on_ticket_resolved

            on_ticket_resolved(ticket)
        except Exception:
            pass
    return Response({"ticket": _ticket_to_public(ticket)})


@api_view(["GET"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerWorkflowsRead])
def public_workflow_list(request):
    team = _team(request.user)
    qs = Workflow.objects.filter(team=team).select_related("template", "ticket").prefetch_related("steps")
    ticket_id = request.GET.get("ticket_id")
    if ticket_id:
        qs = qs.filter(ticket_id=ticket_id)
    workflows = [_workflow_to_public(w) for w in qs.order_by("-created_at")[:100]]
    return Response({"workflows": workflows})


@api_view(["GET"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerWorkflowsRead])
def public_workflow_detail(request, workflow_id):
    team = _team(request.user)
    workflow = get_object_or_404(
        Workflow.objects.select_related("template", "ticket").prefetch_related("steps"),
        pk=workflow_id,
        team=team,
    )
    return Response({"workflow": _workflow_to_public(workflow)})


@api_view(["POST"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerTicketsWrite])
def public_workflow_start(request):
    team = _team(request.user)
    template_id = request.data.get("template_id")
    if not template_id:
        return Response({"error": "template_id is required."}, status=400)
    template = get_object_or_404(WorkflowTemplate, pk=template_id)
    if template.team_id and str(template.team_id) != str(team.id):
        return Response({"error": "Template not available for this workspace."}, status=403)
    ticket = None
    ticket_id = request.data.get("ticket_id")
    if ticket_id:
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id, team=team)
    workflow = start_workflow(template=template, ticket=ticket, team=team, started_by=None)
    return Response({"workflow": _workflow_to_public(workflow)}, status=201)


@api_view(["GET"])
@authentication_classes([PartnerAPIKeyAuthentication])
@permission_classes([PartnerRulesRead])
def public_rule_list(request):
    team = _team(request.user)
    qs = Rule.objects.filter(Q(team=team) | Q(team__isnull=True)).order_by("priority", "name")
    return Response({"rules": [_rule_to_public(r) for r in qs]})
