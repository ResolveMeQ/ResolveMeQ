"""Resolve playbook step kb_links (article titles) to published KB articles."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db.models import Q


def resolve_kb_articles_by_titles(
    titles: List[str],
    *,
    team_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not titles:
        return []
    from knowledge_base.models import KnowledgeBaseArticle

    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in titles:
        title = (raw or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        scope = Q(team__isnull=True)
        if team_id:
            scope = Q(team__isnull=True) | Q(team_id=team_id)
        article = (
            KnowledgeBaseArticle.objects.filter(
                title=title,
                is_published=True,
            )
            .filter(scope)
            .order_by("-team_id", "-updated_at")
            .first()
        )
        if article:
            out.append({
                "kb_id": str(article.kb_id),
                "title": article.title,
            })
    return out
