from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from tickets.models import Ticket
from tickets.scoping import active_team_id_for_user

from .constants import ACTION_LABELS, TRIGGER_LABELS, VALID_ACTION_TYPES, VALID_TRIGGERS
from .engine import dispatch_event
from .models import Rule, RuleExecutionLog
from .scoping import rules_queryset_for_user, user_can_edit_rule, user_can_dry_run_rule, user_can_manage_rules
from .validation import normalize_actions, normalize_conditions, validate_trigger
from monitoring.audit import audit_from_request


def _rule_to_dict(rule: Rule, *, can_edit: bool) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "trigger": rule.trigger,
        "conditions": rule.conditions or [],
        "actions": rule.actions or [],
        "is_active": rule.is_active,
        "priority": rule.priority,
        "team_id": str(rule.team_id) if rule.team_id else None,
        "is_global": rule.team_id is None,
        "can_edit": can_edit,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _log_to_dict(log: RuleExecutionLog) -> dict:
    return {
        "id": log.id,
        "rule_id": log.rule_id,
        "rule_name": log.rule.name if log.rule_id else None,
        "trigger": log.trigger,
        "status": log.status,
        "message": log.message,
        "ticket_id": log.ticket_id,
        "workflow_id": str(log.workflow_id) if log.workflow_id else None,
        "executed_at": log.executed_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def automation_metadata(request):
    return Response({
        "triggers": [{"value": t, "label": TRIGGER_LABELS.get(t, t)} for t in sorted(VALID_TRIGGERS)],
        "actions": [{"value": a, "label": ACTION_LABELS.get(a, a)} for a in sorted(VALID_ACTION_TYPES)],
        "condition_ops": [
            {"value": "equals", "label": "Equals"},
            {"value": "not_equals", "label": "Not equals"},
            {"value": "in", "label": "In list"},
        ],
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rule_list_create(request):
    can_manage = user_can_manage_rules(request.user)
    if request.method == "GET":
        qs = rules_queryset_for_user(request.user).order_by("priority", "name")
        return Response({
            "can_manage": can_manage,
            "rules": [_rule_to_dict(r, can_edit=user_can_edit_rule(request.user, r)) for r in qs],
        })

    if not can_manage:
        return Response({"error": "Only the workspace owner can create rules."}, status=403)

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"error": "name is required."}, status=400)
    try:
        trigger = validate_trigger(request.data.get("trigger"))
        conditions = normalize_conditions(request.data.get("conditions"))
        actions = normalize_actions(request.data.get("actions"))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    tid = active_team_id_for_user(request.user)
    team = Team.objects.filter(pk=tid).first() if tid else None
    if getattr(request.user, "is_staff", False) and request.data.get("is_global"):
        team = None
    elif not team:
        return Response({"error": "Select an active workspace before creating a rule."}, status=400)

    rule = Rule.objects.create(
        name=name[:200],
        description=(request.data.get("description") or "").strip(),
        team=team,
        trigger=trigger,
        conditions=conditions,
        actions=actions,
        is_active=bool(request.data.get("is_active", True)),
        priority=int(request.data.get("priority") or 100),
    )
    audit_from_request(
        request,
        event_type="rule.created",
        team=team,
        resource_type="rule",
        resource_id=str(rule.id),
        summary=f"Rule created: {rule.name}",
        metadata={"trigger": rule.trigger},
    )
    return Response({"rule": _rule_to_dict(rule, can_edit=True)}, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def rule_detail(request, rule_id):
    rule = Rule.objects.filter(pk=rule_id).first()
    if not rule or not rules_queryset_for_user(request.user).filter(pk=rule.pk).exists():
        return Response({"error": "Rule not found."}, status=404)

    if request.method == "GET":
        return Response({"rule": _rule_to_dict(rule, can_edit=user_can_edit_rule(request.user, rule))})

    if not user_can_edit_rule(request.user, rule):
        return Response({"error": "You do not have permission to edit this rule."}, status=403)

    if request.method == "DELETE":
        audit_from_request(
            request,
            event_type="rule.deleted",
            team=rule.team,
            resource_type="rule",
            resource_id=str(rule.id),
            summary=f"Rule deleted: {rule.name}",
            metadata={"trigger": rule.trigger},
        )
        rule.delete()
        return Response({"deleted": True})

    updates = {}
    if "name" in request.data:
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "name cannot be empty."}, status=400)
        updates["name"] = name[:200]
    if "description" in request.data:
        updates["description"] = (request.data.get("description") or "").strip()
    if "is_active" in request.data:
        updates["is_active"] = bool(request.data.get("is_active"))
    if "priority" in request.data:
        updates["priority"] = int(request.data.get("priority") or 100)
    try:
        if "trigger" in request.data:
            updates["trigger"] = validate_trigger(request.data.get("trigger"))
        if "conditions" in request.data:
            updates["conditions"] = normalize_conditions(request.data.get("conditions"))
        if "actions" in request.data:
            updates["actions"] = normalize_actions(request.data.get("actions"))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    if updates:
        for field, value in updates.items():
            setattr(rule, field, value)
        rule.save(update_fields=list(updates.keys()) + ["updated_at"])
        audit_from_request(
            request,
            event_type="rule.updated",
            team=rule.team,
            resource_type="rule",
            resource_id=str(rule.id),
            summary=f"Rule updated: {rule.name}",
            metadata={"fields": list(updates.keys())},
        )

    return Response({"rule": _rule_to_dict(rule, can_edit=True)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rule_dry_run(request, rule_id):
    rule = Rule.objects.filter(pk=rule_id).first()
    if not rule or not rules_queryset_for_user(request.user).filter(pk=rule.pk).exists():
        return Response({"error": "Rule not found."}, status=404)
    if not user_can_dry_run_rule(request.user, rule):
        return Response({"error": "You do not have permission to test this rule."}, status=403)

    ticket_id = request.data.get("ticket_id")
    context = {}
    if ticket_id:
        ticket = Ticket.objects.filter(pk=ticket_id).first()
        if not ticket:
            return Response({"error": "Ticket not found."}, status=404)
        context = {
            "ticket": ticket,
            "category": ticket.category,
            "status": ticket.status,
            "team_id": ticket.team_id,
        }

    log_ids = dispatch_event(rule.trigger, context, dry_run=True, rule_id=rule.id)
    logs = RuleExecutionLog.objects.filter(pk__in=log_ids)
    return Response({"logs": [_log_to_dict(l) for l in logs]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rule_execution_logs(request):
    qs = RuleExecutionLog.objects.filter(
        rule__in=rules_queryset_for_user(request.user),
    ).select_related("rule")[:50]
    return Response({"logs": [_log_to_dict(l) for l in qs]})
