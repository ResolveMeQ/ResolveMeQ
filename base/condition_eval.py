"""Shared field-comparison primitive for rule conditions and step branching.

automation.conditions.evaluate_conditions (rule conditions) and
workflows.branching.should_skip_step (step skip_when) both compare a resolved
field value against an expected value using the same three ops
(equals/not_equals/in) — this is the one place that comparison lives so the
two don't drift apart.
"""

from __future__ import annotations

from typing import Any


def matches(op: str, actual: Any, expected: Any) -> bool:
    if op == "equals":
        return str(actual) == str(expected)
    if op == "not_equals":
        return str(actual) != str(expected)
    if op == "in":
        if not isinstance(expected, list):
            return False
        return actual in expected or str(actual) in [str(x) for x in expected]
    return False


def ticket_condition_fields():
    """Ticket fields with a known, enumerable set of values — for building
    field/value pickers in the rules and workflow-branching admin UIs so users
    can select a condition instead of typing it (and mistyping it). Returns a
    list of (field, label, choices) tuples; choices is the (value, label) list
    already used as the field's own Django `choices=`.
    """
    from tickets.models import Ticket

    return [
        ("category", "Category", Ticket.CATEGORY_CHOICES),
        ("status", "Status", Ticket.STATUS_CHOICES),
        ("escalation_priority", "Priority", Ticket.ESCALATION_PRIORITY_CHOICES),
        ("reported_platform", "Platform", Ticket.PLATFORM_CHOICES),
    ]
