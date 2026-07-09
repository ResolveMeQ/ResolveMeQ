"""Resolve playbook bundle assets (KB articles, resolution templates)."""

from __future__ import annotations

from typing import Any, Dict, List


def resolve_resolution_templates_by_names(names: List[str]) -> List[Dict[str, Any]]:
    if not names:
        return []
    from tickets.models import ResolutionTemplate

    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in names:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        template = (
            ResolutionTemplate.objects.filter(name=name, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if template:
            out.append({
                "id": str(template.id),
                "name": template.name,
                "category": template.category,
                "estimated_time": template.estimated_time,
                "step_count": len(template.steps or []),
            })
    return out
