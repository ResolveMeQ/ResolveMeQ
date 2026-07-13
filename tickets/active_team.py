"""Helpers for UserPreferences.active_team selection."""

from __future__ import annotations

from django.db.models import Q


def user_team_queryset(user):
    from base.models import Team

    if not user or not getattr(user, "is_authenticated", False):
        return Team.objects.none()
    return Team.objects.filter(Q(owner=user) | Q(members=user)).distinct()


def user_can_access_team(user, team_id) -> bool:
    if not team_id:
        return False
    return user_team_queryset(user).filter(pk=team_id).exists()


def maybe_auto_select_active_team(user, *, prefer_team=None):
    """
    If active_team is unset or invalid, select the only workspace the user belongs to.
    Returns UserPreferences (created if needed).
    """
    from base.models import UserPreferences

    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    current_id = prefs.active_team_id
    if current_id and user_can_access_team(user, current_id):
        return prefs

    if prefer_team and user_can_access_team(user, prefer_team.pk):
        prefs.active_team = prefer_team
        prefs.save(update_fields=["active_team"])
        return prefs

    teams = list(user_team_queryset(user).order_by("name")[:2])
    if len(teams) == 1:
        prefs.active_team = teams[0]
        prefs.save(update_fields=["active_team"])
    elif current_id and not user_can_access_team(user, current_id):
        prefs.active_team = None
        prefs.save(update_fields=["active_team"])
    return prefs


def set_active_team_if_unset(user, team):
    """Set active workspace when user has none (e.g. after accepting an invite)."""
    from base.models import UserPreferences

    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    if prefs.active_team_id:
        return prefs
    if team and user_can_access_team(user, team.pk):
        prefs.active_team = team
        prefs.save(update_fields=["active_team"])
    return prefs
