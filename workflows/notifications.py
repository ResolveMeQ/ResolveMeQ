"""
In-app notifications for workflow step transitions, with Slack/Teams fan-out via integrations.notify.
"""
from base.models import InAppNotification


def _team_recipients(team):
    if not team:
        return []
    recipients = list(team.members.all())
    if team.owner and team.owner not in recipients:
        recipients.append(team.owner)
    return recipients


def notify_team_step_active(workflow, step):
    """In-app + Slack/Teams when a new step needs attention."""
    link = f"/tickets/{workflow.ticket_id}" if workflow.ticket_id else "/workflows"
    for user in _team_recipients(workflow.team):
        InAppNotification.objects.create(
            user=user,
            type=InAppNotification.Type.INFO,
            title="New workflow step",
            message=f"\"{step.title}\" is ready to work on ({workflow.template.name if workflow.template_id else 'Workflow'}).",
            link=link,
        )
    try:
        from integrations.notify import notify_workflow_step_active as _external

        _external(workflow, step)
    except Exception:
        pass


def notify_requester_workflow_completed(workflow):
    """Customer-facing: only fires for ticket-linked workflows, once the whole thing is done."""
    if not workflow.ticket_id:
        return
    ticket = workflow.ticket
    InAppNotification.objects.create(
        user=ticket.user,
        type=InAppNotification.Type.SUCCESS,
        title="Your request is complete",
        message=f"Everything for \"{ticket.issue_type}\" has been taken care of.",
        link=f"/tickets/{ticket.ticket_id}",
    )
