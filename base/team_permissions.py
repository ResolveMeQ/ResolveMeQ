"""Workspace-level permission helpers (owner vs scoped delegation)."""

from __future__ import annotations

from tickets.scoping import active_team_id_for_user

from base.workspace_permissions import (
    PERMISSION_FIELDS,
    grant_has_any_permission,
    model_fields_from_permissions,
    normalize_permissions_payload,
    owner_permissions_dict,
    permissions_dict_from_grant,
)


def _team_for_user(user, team=None):
    if team is not None:
        return team
    tid = active_team_id_for_user(user)
    if not tid:
        return None
    from base.models import Team

    return Team.objects.filter(pk=tid).first()


def user_is_team_owner(user, team) -> bool:
    if not user or not user.is_authenticated or not team:
        return False
    return team.owner_id == user.pk


def get_delegation_grant(user, team):
    if not user or not user.is_authenticated or not team:
        return None
    if user_is_team_owner(user, team):
        return None
    from base.models import TeamWorkspaceAdmin

    return TeamWorkspaceAdmin.objects.filter(team_id=team.pk, user_id=user.pk).first()


def user_has_team_permission(user, team, permission_key: str) -> bool:
    if not user or not user.is_authenticated or not team:
        return False
    if permission_key not in PERMISSION_FIELDS:
        return False
    if getattr(user, "is_staff", False):
        return True
    if user_is_team_owner(user, team):
        return True
    grant = get_delegation_grant(user, team)
    if not grant:
        return False
    return bool(getattr(grant, PERMISSION_FIELDS[permission_key], False))


def effective_permissions_for_user(user, team) -> dict[str, bool]:
    if not user or not user.is_authenticated or not team:
        return {key: False for key in PERMISSION_FIELDS}
    if getattr(user, "is_staff", False) or user_is_team_owner(user, team):
        return owner_permissions_dict()
    grant = get_delegation_grant(user, team)
    return permissions_dict_from_grant(grant)


def user_is_workspace_admin(user, team) -> bool:
    """Has any delegated permission (used for badges)."""
    if user_is_team_owner(user, team):
        return False
    grant = get_delegation_grant(user, team)
    return grant is not None and grant_has_any_permission(grant)


def user_can_manage_playbooks(user, team=None) -> bool:
    team = _team_for_user(user, team)
    if not team:
        return False
    return user_has_team_permission(user, team, "manage_playbooks")


def user_can_manage_team_members(user, team) -> bool:
    return user_has_team_permission(user, team, "manage_members")


def user_can_manage_integrations(user, team=None) -> bool:
    team = _team_for_user(user, team)
    if not team:
        return False
    return user_has_team_permission(user, team, "manage_integrations")


def user_can_manage_webhooks(user, team=None) -> bool:
    team = _team_for_user(user, team)
    if not team:
        return False
    return user_has_team_permission(user, team, "manage_webhooks")


def user_can_manage_partner_api(user, team=None) -> bool:
    team = _team_for_user(user, team)
    if not team:
        return False
    return user_has_team_permission(user, team, "manage_partner_api")


def user_can_view_audit_log(user, team=None) -> bool:
    team = _team_for_user(user, team)
    if not team:
        return False
    return user_has_team_permission(user, team, "view_audit_log")


def delegations_for_team(team):
    from base.models import TeamWorkspaceAdmin

    return TeamWorkspaceAdmin.objects.filter(team=team).select_related("user", "granted_by")


def delegation_map_for_team(team) -> dict:
    return {grant.user_id: grant for grant in delegations_for_team(team)}


def workspace_admin_user_ids(team) -> set:
    return {uid for uid, grant in delegation_map_for_team(team).items() if grant_has_any_permission(grant)}


def apply_permissions_to_grant(grant, permissions: dict) -> None:
    for field, value in model_fields_from_permissions(permissions).items():
        setattr(grant, field, value)


def revoke_workspace_admin(team, user) -> bool:
    from base.models import TeamWorkspaceAdmin

    deleted, _ = TeamWorkspaceAdmin.objects.filter(team=team, user=user).delete()
    return deleted > 0


def upsert_delegation(*, team, user, granted_by, permissions_raw) -> tuple[object, bool, dict[str, bool]]:
    from base.models import TeamWorkspaceAdmin

    permissions = normalize_permissions_payload(permissions_raw)
    if not any(permissions.values()):
        revoked = revoke_workspace_admin(team, user)
        return None, False, permissions
    fields = model_fields_from_permissions(permissions)
    grant, created = TeamWorkspaceAdmin.objects.get_or_create(
        team=team,
        user=user,
        defaults={"granted_by": granted_by, **fields},
    )
    if not created:
        apply_permissions_to_grant(grant, permissions)
        grant.granted_by = granted_by
        grant.save()
    return grant, created, permissions
