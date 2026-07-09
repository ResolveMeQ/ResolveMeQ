"""Resolve playbook step kb_links (article titles) to published global KB articles."""

from __future__ import annotations

from typing import Any, Dict, List


def resolve_kb_articles_by_titles(titles: List[str]) -> List[Dict[str, Any]]:
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
        article = (
            KnowledgeBaseArticle.objects.filter(
                title=title,
                is_published=True,
                team__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if article:
            out.append({
                "kb_id": str(article.kb_id),
                "title": article.title,
            })
    return out
