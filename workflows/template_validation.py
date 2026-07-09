"""Validate and normalize WorkflowTemplate.steps JSON."""

from __future__ import annotations

from typing import Any, Dict, List

from .assignee_roles import VALID_ASSIGNEE_ROLE_SLUGS
from .auto_check_validation import normalize_auto_check

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
        assignee_role = (step.get("assignee_role") or "").strip()
        if assignee_role not in VALID_ASSIGNEE_ROLE_SLUGS:
            raise ValueError(f"step {idx + 1} has invalid assignee_role")
        skip_when = step.get("skip_when")
        if skip_when is not None and not isinstance(skip_when, dict):
            raise ValueError(f"step {idx + 1} skip_when must be an object")
        normalized = {
            "title": title[:200],
            "description": (step.get("description") or "").strip(),
            "assignee_team": (step.get("assignee_team") or "").strip()[:100],
            "assignee_role": assignee_role,
            "step_type": step_type,
            "due_days": due_days,
            "auto_complete": bool(step.get("auto_complete", False)),
            "auto_assign": auto_assign,
        }
        if skip_when:
            normalized["skip_when"] = skip_when
        kb_links = step.get("kb_links")
        if kb_links is not None:
            if not isinstance(kb_links, list) or not all(isinstance(x, str) for x in kb_links):
                raise ValueError(f"step {idx + 1} kb_links must be a list of article titles")
            cleaned = [x.strip()[:200] for x in kb_links if (x or "").strip()]
            if cleaned:
                normalized["kb_links"] = cleaned[:5]
        auto_check = step.get("auto_check")
        if auto_check is not None:
            normalized["auto_check"] = normalize_auto_check(auto_check, step_index=idx)
        elif step_type == "auto_check":
            raise ValueError(f"step {idx + 1} auto_check step requires auto_check config")
        out.append(normalized)
    return out
