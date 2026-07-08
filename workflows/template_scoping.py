"""Permissions for workflow template administration."""

from tickets.scoping import active_team_id_for_user

from .models import WorkflowTemplate


def user_can_edit_template(user, template: WorkflowTemplate) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    if template.team_id is None:
        return False
    return template.team.owner_id == user.pk


def user_can_manage_templates(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    tid = active_team_id_for_user(user)
    if not tid:
        return False
    from base.models import Team

    team = Team.objects.filter(pk=tid).first()
    return bool(team and team.owner_id == user.pk)
