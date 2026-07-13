"""Validate rule JSON payloads."""

from __future__ import annotations

from typing import Any, Dict, List

from .constants import VALID_ACTION_TYPES, VALID_CONDITION_OPS, VALID_TRIGGERS


def normalize_conditions(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("conditions must be a list")
    out = []
    for idx, cond in enumerate(raw):
        if not isinstance(cond, dict):
            raise ValueError(f"condition {idx + 1} must be an object")
        field = (cond.get("field") or "").strip()
        if not field:
            raise ValueError(f"condition {idx + 1} requires field")
        op = (cond.get("op") or "equals").strip()
        if op not in VALID_CONDITION_OPS:
            raise ValueError(f"condition {idx + 1} has invalid op")
        out.append({"field": field, "op": op, "value": cond.get("value")})
    return out


def normalize_actions(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("at least one action is required")
    out = []
    for idx, action in enumerate(raw):
        if not isinstance(action, dict):
            raise ValueError(f"action {idx + 1} must be an object")
        action_type = (action.get("type") or "").strip()
        if action_type not in VALID_ACTION_TYPES:
            raise ValueError(f"action {idx + 1} has invalid type")
        normalized = {"type": action_type}
        for key, val in action.items():
            if key != "type":
                normalized[key] = val
        if action_type == "start_workflow":
            if not normalized.get("template_id") and not (normalized.get("template_trigger_category") or "").strip():
                raise ValueError(f"action {idx + 1} start_workflow needs template_id or template_trigger_category")
        if action_type == "set_field":
            if not (normalized.get("field") or "").strip():
                raise ValueError(f"action {idx + 1} set_field requires field")
        if action_type == "call_webhook":
            if not (normalized.get("url") or "").strip():
                raise ValueError(f"action {idx + 1} call_webhook requires url")
        out.append(normalized)
    return out


def validate_trigger(trigger: str) -> str:
    t = (trigger or "").strip()
    if t not in VALID_TRIGGERS:
        raise ValueError("invalid trigger")
    return t


def normalize_cron_expression(trigger: str, cron_expression) -> str:
    """cron_expression is only meaningful (and required) for schedule.cron rules."""
    expr = (cron_expression or "").strip()
    if trigger != "schedule.cron":
        return ""
    if not expr:
        raise ValueError("cron_expression is required when trigger is schedule.cron")
    from croniter import croniter

    if not croniter.is_valid(expr):
        raise ValueError("cron_expression must be a valid 5-field cron expression, e.g. '0 9 * * 1'")
    return expr
