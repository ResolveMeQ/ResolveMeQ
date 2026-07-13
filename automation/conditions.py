"""Evaluate rule conditions against an event context."""

from __future__ import annotations

from typing import Any, Dict, List

from base.condition_eval import matches

from .constants import VALID_CONDITION_OPS


def _context_value(ctx: Dict[str, Any], field: str):
    if not field:
        return None
    if field in ctx:
        return ctx[field]
    ticket = ctx.get("ticket")
    if ticket is not None:
        return getattr(ticket, field, None)
    workflow = ctx.get("workflow")
    if workflow is not None:
        return getattr(workflow, field, None)
    step = ctx.get("step")
    if step is not None:
        return getattr(step, field, None)
    return None


def evaluate_conditions(conditions: List[dict], ctx: Dict[str, Any]) -> bool:
    """All conditions must pass (AND). Empty list = always true."""
    if not conditions:
        return True
    if not isinstance(conditions, list):
        return False
    for cond in conditions:
        if not isinstance(cond, dict):
            return False
        field = (cond.get("field") or "").strip()
        op = (cond.get("op") or "equals").strip()
        expected = cond.get("value")
        if op not in VALID_CONDITION_OPS:
            return False
        actual = _context_value(ctx, field)
        if not matches(op, actual, expected):
            return False
    return True
