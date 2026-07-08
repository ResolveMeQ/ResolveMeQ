"""Simple per-step skip rules evaluated when a workflow is instantiated from a ticket."""

from __future__ import annotations

from typing import Any


def _ticket_field_value(ticket, field_name: str):
    if not ticket or not field_name:
        return None
    return getattr(ticket, field_name, None)


def should_skip_step(step_def: dict, ticket) -> bool:
    """
    skip_when examples:
      {"ticket_field": "category", "equals": "onboarding"}
      {"ticket_field": "reported_platform", "in": ["linux", "macos"]}
    """
    skip = step_def.get("skip_when")
    if not skip or not isinstance(skip, dict) or not ticket:
        return False
    field = (skip.get("ticket_field") or "category").strip()
    value = _ticket_field_value(ticket, field)
    if "equals" in skip:
        return str(value) == str(skip["equals"])
    if "in" in skip and isinstance(skip["in"], list):
        return value in skip["in"]
    if "not_equals" in skip:
        return str(value) != str(skip["not_equals"])
    return False
