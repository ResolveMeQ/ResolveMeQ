"""Validate auto_check config per connector."""

from __future__ import annotations

CONNECTOR_CHECKS = {
    "okta": frozenset({"user_exists", "group_member"}),
    "google_workspace": frozenset({"user_exists", "has_license"}),
    "microsoft365": frozenset({"user_exists", "has_license"}),
}

VALID_AUTO_CHECK_CONNECTORS = frozenset(CONNECTOR_CHECKS.keys())
VALID_EMAIL_FROM = frozenset({"ticket_reporter"})


def normalize_auto_check(auto_check: dict, *, step_index: int) -> dict:
    if not isinstance(auto_check, dict):
        raise ValueError(f"step {step_index + 1} auto_check must be an object")
    connector = (auto_check.get("connector") or "").strip().lower()
    check = (auto_check.get("check") or "").strip()
    email_from = (auto_check.get("email_from") or "ticket_reporter").strip()
    if connector not in VALID_AUTO_CHECK_CONNECTORS:
        raise ValueError(f"step {step_index + 1} auto_check has invalid connector")
    allowed = CONNECTOR_CHECKS.get(connector, frozenset())
    if check not in allowed:
        raise ValueError(f"step {step_index + 1} auto_check has invalid check for {connector}")
    if email_from not in VALID_EMAIL_FROM:
        raise ValueError(f"step {step_index + 1} auto_check has invalid email_from")
    ac_norm = {
        "connector": connector,
        "check": check,
        "email_from": email_from,
    }
    if check == "group_member":
        group_id = (auto_check.get("group_id") or "").strip()
        if not group_id:
            raise ValueError(f"step {step_index + 1} group_member check requires group_id")
        ac_norm["group_id"] = group_id[:128]
    if check == "has_license":
        sku_id = (auto_check.get("sku_id") or "").strip()
        if not sku_id:
            raise ValueError(f"step {step_index + 1} has_license check requires sku_id")
        ac_norm["sku_id"] = sku_id[:128]
    return ac_norm
