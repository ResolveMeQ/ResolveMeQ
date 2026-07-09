"""
Shared workflow instantiation, used by both the manual "start workflow" endpoint
and the automatic ticket-creation trigger (tickets/services.py).
"""
from datetime import timedelta

from django.utils import timezone

from .assignee_roles import role_label
from .branching import should_skip_step
from .models import Workflow, WorkflowStep, WorkflowTemplate

DEFAULT_STEP_DUE_DAYS = 2


def _step_due_days_from_template(workflow, order_index: int) -> int:
    template = workflow.template
    if not template:
        return DEFAULT_STEP_DUE_DAYS
    steps = template.steps or []
    if order_index < 0 or order_index >= len(steps):
        return DEFAULT_STEP_DUE_DAYS
    raw = steps[order_index].get("due_days", DEFAULT_STEP_DUE_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_STEP_DUE_DAYS
    return max(0, days)


def _workflow_sla_days(template: WorkflowTemplate) -> int:
    steps = template.steps or []
    if not steps:
        return 7
    total = 0
    for idx, step in enumerate(steps):
        raw = step.get("due_days", DEFAULT_STEP_DUE_DAYS)
        try:
            total += max(0, int(raw))
        except (TypeError, ValueError):
            total += DEFAULT_STEP_DUE_DAYS
    return max(total, 1)


def _apply_branching_skips(workflow, ticket):
    template = workflow.template
    if not template or not ticket:
        return
    steps_def = template.steps or []
    for step in workflow.steps.order_by("order_index"):
        if step.order_index >= len(steps_def):
            continue
        if should_skip_step(steps_def[step.order_index], ticket):
            step.status = "skipped"
            step.save(update_fields=["status"])


def maybe_notify_workflow_sla_breach(workflow):
    if workflow.status != "in_progress" or not workflow.due_at:
        return
    if workflow.due_at >= timezone.now():
        return
    if workflow.sla_breached_notified_at:
        return
    try:
        from .notifications import notify_workflow_sla_breach

        notify_workflow_sla_breach(workflow)
        workflow.sla_breached_notified_at = timezone.now()
        workflow.save(update_fields=["sla_breached_notified_at"])
    except Exception:
        pass


def _resolve_auto_assign(kind, workflow):
    if kind == "started_by":
        return workflow.started_by
    if kind == "ticket_reporter" and workflow.ticket_id:
        return workflow.ticket.user
    return None


def finalize_workflow(workflow):
    """Customer notifications and ticket sync when a workflow finishes."""
    try:
        from .notifications import notify_requester_workflow_completed

        notify_requester_workflow_completed(workflow)
    except Exception:
        pass
    if workflow.ticket_id:
        ticket = workflow.ticket
        if ticket.status not in ("resolved", "closed"):
            ticket.status = "resolved"
            ticket.save(update_fields=["status", "updated_at"])
            try:
                from automation.hooks import on_ticket_resolved
                on_ticket_resolved(ticket)
            except Exception:
                pass


def _activate_next_steps(workflow):
    """
    Activates the next pending step, resolving any chain of consecutive auto_complete
    steps immediately, and applying auto_assign to the first real (human-actionable)
    step it reaches. Returns True if the workflow is now fully completed.
    """
    while True:
        next_step = workflow.steps.filter(status="pending").order_by("order_index").first()
        if not next_step:
            workflow.status = "completed"
            workflow.save(update_fields=["status"])
            finalize_workflow(workflow)
            return True

        next_step.status = "active"
        if next_step.auto_assign:
            next_step.claimed_by = _resolve_auto_assign(next_step.auto_assign, workflow)
        due_days = _step_due_days_from_template(workflow, next_step.order_index)
        if due_days > 0:
            next_step.due_at = timezone.now() + timedelta(days=due_days)
        next_step.save(update_fields=["status", "claimed_by", "due_at"])

        if next_step.auto_complete:
            next_step.status = "done"
            next_step.completed_at = timezone.now()
            next_step.save(update_fields=["status", "completed_at"])
            try:
                from automation.hooks import on_workflow_step_completed
                on_workflow_step_completed(workflow, next_step)
            except Exception:
                pass
            continue  # keep advancing through the chain

        from .connector_autocomplete import try_auto_complete_connector_step

        if try_auto_complete_connector_step(workflow, next_step):
            continue

        from .child_tickets import spawn_child_ticket_for_step

        spawn_child_ticket_for_step(workflow, next_step)

        try:
            from .notifications import notify_team_step_active

            notify_team_step_active(workflow, next_step)
        except Exception:
            pass
        return False


def start_workflow(*, template: WorkflowTemplate, ticket=None, team=None, started_by=None) -> Workflow:
    """
    Instantiate a Workflow + its WorkflowSteps from a template's `steps` JSON.
    All steps start `pending`; _activate_next_steps resolves the first active one
    (and any leading auto_complete chain) right after creation.
    """
    workflow = Workflow.objects.create(
        ticket=ticket,
        template=template,
        team=team,
        started_by=started_by,
    )
    sla_days = _workflow_sla_days(template)
    workflow.due_at = timezone.now() + timedelta(days=sla_days)
    workflow.save(update_fields=["due_at"])
    steps = template.steps or []
    WorkflowStep.objects.bulk_create([
        WorkflowStep(
            workflow=workflow,
            order_index=idx,
            title=step.get("title", ""),
            description=step.get("description", ""),
            assignee_team=(step.get("assignee_team") or "").strip() or role_label(step.get("assignee_role", "")),
            assignee_role=(step.get("assignee_role") or "").strip(),
            auto_complete=bool(step.get("auto_complete", False)),
            auto_assign=step.get("auto_assign", "") or "",
            step_type=(step.get("step_type") or "manual"),
            status="pending",
        )
        for idx, step in enumerate(steps)
    ])
    _apply_branching_skips(workflow, ticket)
    _activate_next_steps(workflow)
    maybe_notify_workflow_sla_breach(workflow)
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
