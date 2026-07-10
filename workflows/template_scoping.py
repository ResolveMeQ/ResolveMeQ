"""Permissions for workflow template administration."""

from base.team_permissions import user_can_manage_playbooks, user_has_team_permission

from .models import WorkflowTemplate


def user_can_edit_template(user, template: WorkflowTemplate) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    if template.team_id is None:
        return False
    return user_has_team_permission(user, template.team, "manage_playbooks")


def user_can_manage_templates(user) -> bool:
    return user_can_manage_playbooks(user)
