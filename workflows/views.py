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
from .notifications import notify_requester_workflow_completed
from .scoping import user_can_access_workflow, workflows_queryset_for_user
from .services import _activate_next_steps, start_workflow


def _step_to_dict(step):
    return {
        "id": step.id,
        "order_index": step.order_index,
        "title": step.title,
        "description": step.description,
        "assignee_team": step.assignee_team,
        "status": step.status,
        "claimed_by": step.claimed_by_id and {
            "id": str(step.claimed_by_id),
            "name": step.claimed_by.get_full_name() or step.claimed_by.email or step.claimed_by.username,
        },
        "completed_at": step.completed_at,
    }


def _workflow_to_dict(workflow):
    steps = list(workflow.steps.all())
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
        "steps": [_step_to_dict(s) for s in steps],
        "steps_done": sum(1 for s in steps if s.status == "done"),
        "steps_total": len(steps),
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
        return Response({"workflows": [_workflow_to_dict(w) for w in qs.order_by("-created_at")]})

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
    return Response({"workflow": _workflow_to_dict(workflow)}, status=201)


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

    # Race-safe claim -- exact pattern as tickets.views.assign_ticket's escalation claim.
    updated = WorkflowStep.objects.filter(pk=step.pk, status="active", claimed_by__isnull=True).update(
        claimed_by=request.user
    )
    step.refresh_from_db()
    if not updated:
        return Response(
            {"error": "This step is not claimable (already claimed, not active yet, or done).", "step": _step_to_dict(step)},
            status=409,
        )
    return Response({"step": _step_to_dict(step)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_step(request, workflow_id, step_id):
    workflow = get_object_or_404(Workflow, pk=workflow_id)
    if not user_can_access_workflow(request.user, workflow):
        return Response({"error": "You do not have permission to access this workflow."}, status=403)
    step = get_object_or_404(WorkflowStep, pk=step_id, workflow=workflow)

    if step.status != "active":
        return Response({"error": "Only the active step can be completed.", "step": _step_to_dict(step)}, status=409)

    step.status = "done"
    step.completed_at = timezone.now()
    step.save(update_fields=["status", "completed_at"])

    completed_whole_workflow = _activate_next_steps(workflow)
    if completed_whole_workflow:
        try:
            notify_requester_workflow_completed(workflow)
        except Exception:
            pass

    return Response({"workflow": _workflow_to_dict(workflow)})
