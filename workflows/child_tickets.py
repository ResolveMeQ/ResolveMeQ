"""Cross-ticket workflows — spawn child tickets per step (P3-4)."""

from __future__ import annotations

import logging
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)

ROLE_CHILD_CATEGORY = {
    "facilities": "access",
    "it": "provisioning",
    "hr": "onboarding",
    "security": "security",
}


def get_spawn_config(workflow, step) -> Optional[dict]:
    template = workflow.template
    if not template:
        return None
    steps = template.steps or []
    idx = step.order_index
    if idx < 0 or idx >= len(steps):
        return None
    cfg = steps[idx]
    if not cfg.get("spawn_child_ticket"):
        return None
    return cfg


def _child_issue_type(workflow, step) -> str:
    parent = workflow.ticket
    base = step.title or "Workflow step"
    if parent and parent.issue_type:
        suffix = parent.issue_type[:80]
        text = f"{base} — {suffix}"
    elif workflow.template_id:
        text = f"{base} — {workflow.template.name}"
    else:
        text = base
    return text[:100]


def _child_description(workflow, step) -> str:
    lines = [
        f"Child task for workflow step: {step.title}",
        "",
        step.description or "",
        "",
    ]
    if workflow.ticket_id:
        lines.append(f"Parent ticket: #{workflow.ticket_id}")
    lines.append(f"Workflow: {workflow.id}")
    return "\n".join(line for line in lines if line is not None).strip()


def spawn_child_ticket_for_step(workflow, step):
    """Create a linked child ticket when a step becomes active (idempotent)."""
    if step.child_ticket_id:
        return step.child_ticket

    cfg = get_spawn_config(workflow, step)
    if not cfg:
        return None

    from tickets.models import Ticket, TicketInteraction

    parent = workflow.ticket
    reporter = parent.user if parent else workflow.started_by
    if not reporter:
        logger.warning("Cannot spawn child ticket — no reporter for workflow %s", workflow.id)
        return None

    category = (cfg.get("child_ticket_category") or "").strip()
    if not category:
        category = ROLE_CHILD_CATEGORY.get(step.assignee_role or "", "other")

    valid_categories = {c[0] for c in Ticket.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = "other"

    child = Ticket.objects.create(
        user=reporter,
        team=workflow.team or (parent.team if parent else None),
        issue_type=_child_issue_type(workflow, step),
        status="open",
        description=_child_description(workflow, step),
        category=category,
        tags=["workflow_child", f"workflow:{workflow.id}", f"step:{step.id}"],
    )
    TicketInteraction.objects.create(
        ticket=child,
        user=reporter,
        interaction_type="user_message",
        content=f"Spawned from workflow step \"{step.title}\" (parent #{parent.ticket_id if parent else '—'}).",
    )

    step.child_ticket = child
    step.save(update_fields=["child_ticket"])

    try:
        from base.models import InAppNotification

        link = f"/tickets?highlight={child.ticket_id}"
        InAppNotification.objects.create(
            user=reporter,
            type=InAppNotification.Type.INFO,
            title="Workflow task created",
            message=f"Ticket #{child.ticket_id} opened for \"{step.title}\".",
            link=link,
        )
    except Exception as exc:
        logger.warning("Child ticket notification failed: %s", exc)

    logger.info(
        "Spawned child ticket %s for workflow %s step %s",
        child.ticket_id,
        workflow.id,
        step.id,
    )
    return child


def maybe_complete_step_for_resolved_child(ticket) -> bool:
    """When a child ticket is resolved, mark its workflow step done and advance."""
    from .models import WorkflowStep
    from .services import _activate_next_steps

    step = (
        WorkflowStep.objects.filter(child_ticket=ticket, status="active")
        .select_related("workflow")
        .first()
    )
    if not step:
        return False

    workflow = step.workflow
    step.status = "done"
    step.completed_at = timezone.now()
    step.save(update_fields=["status", "completed_at"])

    try:
        from automation.hooks import on_workflow_step_completed

        on_workflow_step_completed(workflow, step)
    except Exception as exc:
        logger.warning("Workflow step completed hook failed: %s", exc)

    _activate_next_steps(workflow)
    logger.info(
        "Child ticket %s resolved — completed workflow step %s",
        ticket.ticket_id,
        step.id,
    )
    return True
