"""Workspace ops roles for workflow step claim routing."""

from __future__ import annotations

ASSIGNEE_ROLES = [
    ("", "Anyone"),
    ("it", "IT Support"),
    ("hr", "HR"),
    ("facilities", "Facilities"),
    ("security", "Security"),
]

ROLE_LABELS = dict(ASSIGNEE_ROLES)
VALID_ASSIGNEE_ROLE_SLUGS = frozenset(slug for slug, _ in ASSIGNEE_ROLES)


def role_label(slug: str | None) -> str:
    return ROLE_LABELS.get((slug or "").strip(), (slug or "").strip() or "Anyone")
