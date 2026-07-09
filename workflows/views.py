from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from base.models import Team
from tickets.models import Ticket
from tickets.scoping import active_team_id_for_user, user_can_access_ticket

from .models import Workflow, WorkflowStep, WorkflowTemplate
from .scoping import user_can_access_workflow, user_can_claim_step, workflows_queryset_for_user
from .services import _activate_next_steps, maybe_notify_workflow_sla_breach, start_workflow
from .assignee_roles import role_label
from .kb_links import resolve_kb_articles_by_titles
from .auto_checks import get_auto_check_config, latest_check_result, run_auto_check
from .step_assistant import accept_step_assistant_suggestion, get_step_assistant_suggestions


def _kb_articles_for_step(workflow, order_index: int):
    template = workflow.template
    if not template:
        return []
    steps = template.steps or []
    if order_index < 0 or order_index >= len(steps):
        return []
    return resolve_kb_articles_by_titles(steps[order_index].get("kb_links") or [])


def _step_is_overdue(step, now=None):
    now = now or timezone.now()
    return (
        step.status == "active"
        and step.due_at is not None
        and step.due_at < now
    )


def _workflow_is_overdue(workflow, now=None):
    now = now or timezone.now()
    if workflow.status != "in_progress":
        return False
    if workflow.due_at and workflow.due_at < now:
        return True
    return False


def _step_to_dict(step, now=None, user=None):
    now = now or timezone.now()
    can_claim = False
    if user and step.status == "active" and not step.claimed_by_id:
        can_claim = user_can_claim_step(user, step)
    return {
        "id": step.id,
        "order_index": step.order_index,
        "title": step.title,
        "description": step.description,
        "assignee_team": step.assignee_team,
        "assignee_role": step.assignee_role or "",
        "assignee_role_label": role_label(step.assignee_role),
        "step_type": step.step_type,
        "status": step.status,
        "due_at": step.due_at,
        "is_overdue": _step_is_overdue(step, now),
        "can_claim": can_claim,
        "kb_articles": _kb_articles_for_step(step.workflow, step.order_index),
        "auto_check": get_auto_check_config(step.workflow, step),
        "auto_check_result": latest_check_result(step),
        "auto_verified": (
            step.status == "done"
            and step.step_type == "auto_check"
            and (latest_check_result(step) or {}).get("status") == "success"
        ),
        "claimed_by": step.claimed_by_id and {
            "id": str(step.claimed_by_id),
            "name": step.claimed_by.get_full_name() or step.claimed_by.email or step.claimed_by.username,
        },
        "completed_at": step.completed_at,
    }


def _workflow_to_dict(workflow, now=None, user=None):
    now = now or timezone.now()
    steps = list(workflow.steps.all())
    overdue_count = sum(1 for s in steps if _step_is_overdue(s, now))
    wf_overdue = _workflow_is_overdue(workflow, now)
    return {
        "id": str(workflow.id),
        "status": workflow.status,
        "template_name": workflow.template.name if workflow.template_id else None,
        "ticket_id": workflow.ticket_id,
        "ticket_issue_type": workflow.ticket.issue_type if workflow.ticket_id else None,
        "started_by": workflow.started_by_id and (
            workflow.started_by.get_full_name() or workflow.started_by.email or workflow.started_by.username
        ),
        "created_at": workflow.created_at,
        "due_at": workflow.due_at,
        "is_overdue": wf_overdue or overdue_count > 0,
        "workflow_sla_breached": wf_overdue,
        "steps": [_step_to_dict(s, now, user) for s in steps],
        "steps_done": sum(1 for s in steps if s.status == "done"),
        "steps_total": len(steps),
        "overdue_step_count": overdue_count,
        "has_overdue": wf_overdue or overdue_count > 0,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def workflow_list_create(request):
    """
    GET: workflows visible to the caller, optionally filtered to one ticket (?ticket=<id>).
    POST: start a workflow from a template. Body: {"template_id": <id>, "ticket_id": <id, optional>}.
    """
    if request.method == "GET":
        qs = workflows_queryset_for_user(request.user).select_related("template", "ticket").prefetch_related("steps")
        ticket_id = request.query_params.get("ticket")
        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)
        if request.query_params.get("overdue") == "1":
            now = timezone.now()
            qs = qs.filter(
                Q(steps__status="active", steps__due_at__lt=now)
                | Q(status="in_progress", due_at__lt=now)
            ).distinct()
        now = timezone.now()
        workflows_out = []
        for w in qs.order_by("-created_at"):
            maybe_notify_workflow_sla_breach(w)
            workflows_out.append(_workflow_to_dict(w, now, request.user))
        return Response({"workflows": workflows_out})

    template_id = request.data.get("template_id")
    if not template_id:
        return Response({"error": "template_id is required."}, status=400)
    template = get_object_or_404(WorkflowTemplate, pk=template_id)

    ticket = None
    ticket_id = request.data.get("ticket_id")
    if ticket_id:
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
        if not user_can_access_ticket(request.user, ticket):
            return Response({"error": "You do not have permission to link this ticket."}, status=403)

    tid = active_team_id_for_user(request.user)
    team = Team.objects.filter(pk=tid).first() if tid else None
    if template.team_id and (not team or str(template.team_id) != str(team.id)):
        return Response({"error": "This template is not available to your team."}, status=403)

    workflow = start_workflow(template=template, ticket=ticket, team=team, started_by=request.user)
    return Response({"workflow": _workflow_to_dict(workflow, user=request.user)}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def assignee_roles(request):
    from .assignee_roles import ASSIGNEE_ROLES

    return Response({
        "roles": [{"value": slug, "label": label} for slug, label in ASSIGNEE_ROLES],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def workflow_templates(request):
    """Templates available to the caller's active team: global (team=None) + team-specific."""
    tid = active_team_id_for_user(request.user)
    qs = WorkflowTemplate.objects.filter(Q(team__isnull=True) | Q(team_id=tid)) if tid else WorkflowTemplate.objects.filter(team__isnull=True)
    return Response({
        "templates": [
            {"id": t.id, "name": t.name, "trigger_category": t.trigger_category, "step_count": len(t.steps or [])}
            for t in qs.order_by("name")
        ]
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def claim_step(request, workflow_id, step_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not user_can_access_workflow(request.user, workflow):
        return Response({"error": "You do not have permission to access this workflow."}, status=403)
    step = get_object_or_404(WorkflowStep, pk=step_id, workflow=workflow)

    if not user_can_claim_step(request.user, step):
        return Response(
            {
                "error": "This step is assigned to a different ops role. Ask your workspace owner to update your role.",
                "step": _step_to_dict(step, user=request.user),
            },
            status=403,
        )

    # Race-safe claim -- exact pattern as tickets.views.assign_ticket's escalation claim.
    updated = WorkflowStep.objects.filter(pk=step.pk, status="active", claimed_by__isnull=True).update(
        claimed_by=request.user
    )
    step.refresh_from_db()
    if not updated:
        return Response(
            {"error": "This step is not claimable (already claimed, not active yet, or done).", "step": _step_to_dict(step, user=request.user)},
            status=409,
        )
    return Response({"step": _step_to_dict(step, user=request.user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_step(request, workflow_id, step_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not user_can_access_workflow(request.user, workflow):
        return Response({"error": "You do not have permission to access this workflow."}, status=403)
    step = get_object_or_404(WorkflowStep, pk=step_id, workflow=workflow)

    if step.status != "active":
        return Response({"error": "Only the active step can be completed.", "step": _step_to_dict(step, user=request.user)}, status=409)

    if step.claimed_by_id and step.claimed_by_id != request.user.pk and not user_can_claim_step(request.user, step):
        return Response({"error": "You are not assigned to complete this step.", "step": _step_to_dict(step, user=request.user)}, status=403)

    step.status = "done"
    step.completed_at = timezone.now()
    step.save(update_fields=["status", "completed_at"])

    try:
        from automation.hooks import on_workflow_step_completed

        on_workflow_step_completed(workflow, step)
    except Exception:
        pass

    completed_whole_workflow = _activate_next_steps(workflow)

    return Response({"workflow": _workflow_to_dict(workflow, user=request.user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rerun_auto_check(request, workflow_id, step_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not user_can_access_workflow(request.user, workflow):
        return Response({"error": "You do not have permission to access this workflow."}, status=403)
    step = get_object_or_404(WorkflowStep, pk=step_id, workflow=workflow)

    if step.step_type != "auto_check":
        return Response({"error": "This step is not an auto_check step."}, status=400)
    if step.status != "active":
        return Response({"error": "Auto check can only run on the active step.", "step": _step_to_dict(step, user=request.user)}, status=409)

    passed, message = run_auto_check(step, workflow)
    if passed:
        step.status = "done"
        step.completed_at = timezone.now()
        step.save(update_fields=["status", "completed_at"])
        try:
            from automation.hooks import on_workflow_step_completed
            on_workflow_step_completed(workflow, step)
        except Exception:
            pass
        _activate_next_steps(workflow)

    return Response({
        "passed": passed,
        "message": message,
        "workflow": _workflow_to_dict(workflow, user=request.user),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def step_assistant_suggestions(request, workflow_id, step_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not user_can_access_workflow(request.user, workflow):
        return Response({"error": "You do not have permission to access this workflow."}, status=403)
    step = get_object_or_404(WorkflowStep, pk=step_id, workflow=workflow)

    result = get_step_assistant_suggestions(workflow=workflow, step=step, user=request.user)
    if result.get("error") == "agent_quota_exceeded":
        return Response(result, status=429)
    if result.get("error"):
        return Response(result, status=400)
    return Response({"suggestions": result, "step": _step_to_dict(step, user=request.user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def step_assistant_accept(request, workflow_id, step_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not user_can_access_workflow(request.user, workflow):
        return Response({"error": "You do not have permission to access this workflow."}, status=403)
    step = get_object_or_404(WorkflowStep, pk=step_id, workflow=workflow)

    result = accept_step_assistant_suggestion(
        workflow=workflow,
        step=step,
        user=request.user,
        note=(request.data.get("note") or "").strip(),
    )
    if result.get("error"):
        return Response(result, status=400)
    return Response(result)
