"""Permissions for automation rule administration."""

from django.db.models import Q

from base.team_permissions import user_can_manage_playbooks, user_has_team_permission
from tickets.scoping import active_team_id_for_user

from .models import Rule


def user_can_manage_rules(user) -> bool:
    return user_can_manage_playbooks(user)


def user_can_edit_rule(user, rule: Rule) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    if rule.team_id is None:
        return False
    return user_has_team_permission(user, rule.team, "manage_playbooks")


def user_can_dry_run_rule(user, rule: Rule) -> bool:
    if user_can_edit_rule(user, rule):
        return True
    if rule.team_id is None and user_can_manage_rules(user):
        return True
    return False


def rules_queryset_for_user(user):
    if not user or not user.is_authenticated:
        return Rule.objects.none()
    tid = active_team_id_for_user(user)
    if getattr(user, "is_staff", False):
        return Rule.objects.all()
    if tid:
        return Rule.objects.filter(Q(team_id=tid) | Q(team__isnull=True))
    return Rule.objects.filter(team__isnull=True)
