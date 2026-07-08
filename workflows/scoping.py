"""
Workflow visibility, mirroring tickets/scoping.py's shape.

- Ticket-linked workflows delegate straight to the existing ticket scoping rules (so a platform
  agent's cross-tenant escalation access covers ticket-linked workflows for free).
- Standalone workflows (no ticket) fall back to plain active-team membership -- no platform-agent
  cross-tenant access for these in v1; there's no escalated/claimed anchor to gate that on, and
  nobody has asked for cross-tenant visibility into another team's standalone workflows yet.
"""
from django.db.models import Q

from tickets.scoping import active_team_id_for_user, user_can_access_ticket

from .models import Workflow


def _user_ops_role(user) -> str:
    if not user:
        return ""
    profile = getattr(user, "profile", None)
    return (getattr(profile, "ops_role", None) or "").strip() if profile else ""


def _is_workspace_owner(user, workflow) -> bool:
    team = getattr(workflow, "team", None)
    return bool(team and team.owner_id == user.pk)


def user_can_claim_step(user, step) -> bool:
    """Role-gated claim: empty assignee_role = any workspace member with workflow access."""
    if not user or not user.is_authenticated:
        return False
    workflow = step.workflow
    if not user_can_access_workflow(user, workflow):
        return False
    if _is_workspace_owner(user, workflow):
        return True
    required = (step.assignee_role or "").strip()
    if not required:
        return True
    return _user_ops_role(user) == required


def user_can_access_workflow(user, workflow):
    if not user or not user.is_authenticated:
        return False
    if workflow.ticket_id:
        return user_can_access_ticket(user, workflow.ticket)
    tid = active_team_id_for_user(user)
    return bool(tid) and workflow.team_id is not None and str(workflow.team_id) == str(tid)


def workflows_queryset_for_user(user):
    """Queryset of workflows visible to this user (ticket-linked + standalone, own team only)."""
    if not user or not user.is_authenticated:
        return Workflow.objects.none()
    tid = active_team_id_for_user(user)
    if not tid:
        return Workflow.objects.none()
    return Workflow.objects.filter(Q(team_id=tid) | Q(ticket__team_id=tid))
