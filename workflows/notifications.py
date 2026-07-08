"""
In-app-only notifications for workflow step transitions.

Deliberately NOT Slack/Teams for this pass: the one team-facing Slack broadcast pattern
elsewhere (tickets/notifications.py's notify_support_escalation) posts to a single global
settings.SLACK_ESCALATION_CHANNEL -- that's ResolveMeQ's own internal ops channel, not a
per-customer-team channel, so reusing it here would spam ResolveMeQ's channel with every
customer's workflow activity. The Teams path (escalation_conversation_for_team) is genuinely
per-team, but Teams integration is paused/dormant (Azure cost). In-app notifications are a
real, immediately-live channel with zero new infrastructure -- Slack/Teams team-channel
notification is a real future increment once a per-customer-team default channel exists.
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
    """One InAppNotification per team member (+ owner) that a new step needs attention."""
    link = f"/tickets/{workflow.ticket_id}" if workflow.ticket_id else "/workflows"
    for user in _team_recipients(workflow.team):
        InAppNotification.objects.create(
            user=user,
            type=InAppNotification.Type.INFO,
            title="New workflow step",
            message=f"\"{step.title}\" is ready to work on ({workflow.template.name if workflow.template_id else 'Workflow'}).",
            link=link,
        )


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
