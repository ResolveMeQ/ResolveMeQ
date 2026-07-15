"""Validate auto_action config per connector."""

from __future__ import annotations

CONNECTOR_ACTIONS = {
    "okta": frozenset({"deactivate_user", "reset_password", "remove_from_group"}),
    "google_workspace": frozenset({"deactivate_user", "reset_password", "remove_from_group", "revoke_license"}),
    "microsoft365": frozenset({"deactivate_user", "reset_password", "remove_from_group", "revoke_license"}),
}

VALID_AUTO_ACTION_CONNECTORS = frozenset(CONNECTOR_ACTIONS.keys())
VALID_EMAIL_FROM = frozenset({"ticket_reporter"})


def normalize_auto_action(auto_action: dict, *, step_index: int) -> dict:
    if not isinstance(auto_action, dict):
        raise ValueError(f"step {step_index + 1} auto_action must be an object")
    connector = (auto_action.get("connector") or "").strip().lower()
    action = (auto_action.get("action") or "").strip()
    email_from = (auto_action.get("email_from") or "ticket_reporter").strip()
    if connector not in VALID_AUTO_ACTION_CONNECTORS:
        raise ValueError(f"step {step_index + 1} auto_action has invalid connector")
    allowed = CONNECTOR_ACTIONS.get(connector, frozenset())
    if action not in allowed:
        raise ValueError(f"step {step_index + 1} auto_action has invalid action for {connector}")
    if email_from not in VALID_EMAIL_FROM:
        raise ValueError(f"step {step_index + 1} auto_action has invalid email_from")
    aa_norm = {
        "connector": connector,
        "action": action,
        "email_from": email_from,
    }
    if action == "remove_from_group":
        group_id = (auto_action.get("group_id") or "").strip()
        if not group_id:
            raise ValueError(f"step {step_index + 1} remove_from_group action requires group_id")
        aa_norm["group_id"] = group_id[:128]
    if action == "revoke_license":
        sku_id = (auto_action.get("sku_id") or "").strip()
        if not sku_id:
            raise ValueError(f"step {step_index + 1} revoke_license action requires sku_id")
        aa_norm["sku_id"] = sku_id[:128]
    return aa_norm
