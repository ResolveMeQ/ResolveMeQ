"""Scoped workspace delegation permission keys and labels."""

from __future__ import annotations

# API / frontend keys -> TeamWorkspaceAdmin model fields
PERMISSION_FIELDS: dict[str, str] = {
    "manage_playbooks": "can_manage_playbooks",
    "manage_members": "can_manage_members",
    "manage_integrations": "can_manage_integrations",
    "manage_webhooks": "can_manage_webhooks",
    "manage_partner_api": "can_manage_partner_api",
    "view_audit_log": "can_view_audit_log",
}

PERMISSION_LABELS: dict[str, str] = {
    "manage_playbooks": "Playbooks & automation rules",
    "manage_members": "Members & ops roles",
    "manage_integrations": "Integrations (Google, Microsoft, Okta, Jira, Slack)",
    "manage_webhooks": "Outbound webhooks",
    "manage_partner_api": "Partner API keys",
    "view_audit_log": "Compliance audit log",
}

PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "manage_playbooks": "Create and edit workflow templates and automation rules.",
    "manage_members": "Invite, remove members, and set IT/HR ops roles.",
    "manage_integrations": "Connect and disconnect workspace integrations.",
    "manage_webhooks": "Create, edit, and delete outbound webhook endpoints.",
    "manage_partner_api": "Create and revoke partner API keys.",
    "view_audit_log": "View and export the compliance audit log.",
}

DEFAULT_GRANT_PERMISSIONS: dict[str, bool] = {
    "manage_playbooks": True,
    "manage_members": True,
    "manage_integrations": False,
    "manage_webhooks": False,
    "manage_partner_api": False,
    "view_audit_log": False,
}

OWNER_ONLY_NOTE = "Billing, workspace deletion, and granting permissions stay with the workspace owner."


def permission_scopes_metadata() -> list[dict]:
    return [
        {
            "key": key,
            "label": PERMISSION_LABELS[key],
            "description": PERMISSION_DESCRIPTIONS[key],
            "default": DEFAULT_GRANT_PERMISSIONS[key],
        }
        for key in PERMISSION_FIELDS
    ]


def permissions_dict_from_grant(grant) -> dict[str, bool]:
    if grant is None:
        return {key: False for key in PERMISSION_FIELDS}
    return {key: bool(getattr(grant, field)) for key, field in PERMISSION_FIELDS.items()}


def owner_permissions_dict() -> dict[str, bool]:
    return {key: True for key in PERMISSION_FIELDS}


def grant_has_any_permission(grant) -> bool:
    return any(permissions_dict_from_grant(grant).values())


def normalize_permissions_payload(raw) -> dict[str, bool]:
    """Merge client payload with defaults; returns API-key dict."""
    base = dict(DEFAULT_GRANT_PERMISSIONS)
    if not isinstance(raw, dict):
        return base
    for key in PERMISSION_FIELDS:
        if key in raw:
            base[key] = bool(raw[key])
    return base


def model_fields_from_permissions(permissions: dict[str, bool]) -> dict[str, bool]:
    return {PERMISSION_FIELDS[key]: permissions[key] for key in PERMISSION_FIELDS}


def permissions_from_model_fields(**kwargs) -> dict[str, bool]:
    inverse = {v: k for k, v in PERMISSION_FIELDS.items()}
    out = {key: False for key in PERMISSION_FIELDS}
    for field, value in kwargs.items():
        key = inverse.get(field)
        if key:
            out[key] = bool(value)
    return out
