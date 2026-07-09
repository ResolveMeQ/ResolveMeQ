"""Permissions for automation rule administration."""

from tickets.scoping import active_team_id_for_user

from .models import Rule


def user_can_manage_rules(user) -> bool:
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


def user_can_edit_rule(user, rule: Rule) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    if rule.team_id is None:
        return False
    return rule.team.owner_id == user.pk


def user_can_dry_run_rule(user, rule: Rule) -> bool:
    if user_can_edit_rule(user, rule):
        return True
    if rule.team_id is None and user_can_manage_rules(user):
        return True
    return False


def rules_queryset_for_user(user):
    from django.db.models import Q

    if not user or not user.is_authenticated:
        return Rule.objects.none()
    tid = active_team_id_for_user(user)
    if getattr(user, "is_staff", False):
        return Rule.objects.all()
    if tid:
        return Rule.objects.filter(Q(team_id=tid) | Q(team__isnull=True))
    return Rule.objects.filter(team__isnull=True)
