"""
Shared workflow instantiation, used by both the manual "start workflow" endpoint
and the automatic ticket-creation trigger (tickets/services.py).
"""
from .models import Workflow, WorkflowStep, WorkflowTemplate


def start_workflow(*, template: WorkflowTemplate, ticket=None, team=None, started_by=None) -> Workflow:
    """
    Instantiate a Workflow + its WorkflowSteps from a template's `steps` JSON.
    The first step starts `active`; everything after it starts `pending` --
    that's the entire dependency model for v1 (strictly sequential, no DAG).
    """
    workflow = Workflow.objects.create(
        ticket=ticket,
        template=template,
        team=team,
        started_by=started_by,
    )
    steps = template.steps or []
    created_steps = WorkflowStep.objects.bulk_create([
        WorkflowStep(
            workflow=workflow,
            order_index=idx,
            title=step.get("title", ""),
            description=step.get("description", ""),
            assignee_team=step.get("assignee_team", ""),
            status="active" if idx == 0 else "pending",
        )
        for idx, step in enumerate(steps)
    ])
    if created_steps:
        try:
            from .notifications import notify_team_step_active

            notify_team_step_active(workflow, created_steps[0])
        except Exception:
            pass
    return workflow


def maybe_start_workflow_for_ticket(ticket):
    """
    Called from tickets.services.create_ticket_with_reporter after a ticket is created.
    If the ticket's category matches a WorkflowTemplate.trigger_category (team-scoped first,
    else the global fallback), instantiate that workflow. No-op if no template matches --
    most tickets aren't workflow-shaped requests.
    """
    if not ticket.category:
        return None
    template = (
        WorkflowTemplate.objects.filter(trigger_category=ticket.category, team=ticket.team).first()
        or WorkflowTemplate.objects.filter(trigger_category=ticket.category, team__isnull=True).first()
    )
    if not template:
        return None
    return start_workflow(template=template, ticket=ticket, team=ticket.team, started_by=ticket.user)
