"""Validate and normalize WorkflowTemplate.steps JSON."""

from __future__ import annotations

from typing import Any, Dict, List

VALID_STEP_TYPES = frozenset({"manual", "approval", "auto_check"})
VALID_AUTO_ASSIGN = frozenset({"", "started_by", "ticket_reporter"})


def normalize_template_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_steps, list):
        raise ValueError("steps must be a list")
    if not raw_steps:
        raise ValueError("at least one step is required")
    out: List[Dict[str, Any]] = []
    for idx, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {idx + 1} must be an object")
        title = (step.get("title") or "").strip()
        if not title:
            raise ValueError(f"step {idx + 1} requires a title")
        step_type = (step.get("step_type") or "manual").strip().lower()
        if step_type not in VALID_STEP_TYPES:
            raise ValueError(f"step {idx + 1} has invalid step_type")
        auto_assign = (step.get("auto_assign") or "").strip()
        if auto_assign not in VALID_AUTO_ASSIGN:
            raise ValueError(f"step {idx + 1} has invalid auto_assign")
        due_days_raw = step.get("due_days", 2)
        try:
            due_days = max(0, int(due_days_raw))
        except (TypeError, ValueError):
            due_days = 2
        normalized = {
            "title": title[:200],
            "description": (step.get("description") or "").strip(),
            "assignee_team": (step.get("assignee_team") or "").strip()[:100],
            "step_type": step_type,
            "due_days": due_days,
            "auto_complete": bool(step.get("auto_complete", False)),
            "auto_assign": auto_assign,
        }
        out.append(normalized)
    return out
