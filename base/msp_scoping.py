"""MSP mode scoping and permissions (P3-5)."""

from __future__ import annotations

from typing import Optional

from django.conf import settings


def get_msp_hub_for_user(user, *, team_id=None):
    """Return the MSP hub team the user owns, optionally matching team_id."""
    from base.models import Team

    if not user or not user.is_authenticated:
        return None
    qs = Team.objects.filter(owner=user, team_kind=Team.TEAM_KIND_MSP, is_active=True)
    if team_id:
        qs = qs.filter(pk=team_id)
    return qs.order_by("-created_at").first()


def user_manages_msp_client(user, team) -> bool:
    if not user or not team:
        return False
    if team.team_kind != team.TEAM_KIND_MSP_CLIENT:
        return False
    if team.owner_id == user.id:
        return True
    if team.msp_parent_id and team.msp_parent.owner_id == user.id:
        return True
    return False


def user_can_access_team_as_msp_admin(user, team) -> bool:
    if not user or not team:
        return False
    if team.owner_id == user.id or team.members.filter(pk=user.pk).exists():
        return True
    return user_manages_msp_client(user, team)


def msp_client_teams_for_hub(hub):
    from base.models import Team

    if not hub or hub.team_kind != Team.TEAM_KIND_MSP:
        return Team.objects.none()
    return Team.objects.filter(
        msp_parent=hub,
        team_kind=Team.TEAM_KIND_MSP_CLIENT,
        is_active=True,
    ).order_by("name")


def max_msp_clients_for_hub(hub) -> int:
    return int(getattr(settings, "MSP_MAX_CLIENTS_PER_HUB", 50))


def msp_client_name(hub, client_name: str) -> str:
    """Build a globally unique team name for an MSP client workspace."""
    base = f"{hub.name} — {(client_name or '').strip()}"[:180]
    from base.models import Team

    if not Team.objects.filter(name=base).exists():
        return base
    suffix = str(hub.id)[:8]
    return f"{base} ({suffix})"[:200]
