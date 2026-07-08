"""Generate and persist marketing blog posts via the ResolveMeQ AI agent."""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from base.agent_http import get_agent_service_headers
from base.models import BlogPost

logger = logging.getLogger(__name__)

_BLOG_CATEGORIES = (
    "AI & Automation",
    "Best Practices",
    "Strategy",
    "Knowledge Base",
    "Analytics",
)


def _agent_blog_post_url() -> str:
    raw = getattr(
        settings,
        "AI_AGENT_URL",
        "https://agent.resolvemeq.net/tickets/analyze/",
    )
    u = str(raw).strip()
    if "blog-post" in u.lower():
        return u
    for needle, repl in (
        ("/tickets/analyze/", "/tickets/blog-post/"),
        ("/tickets/analyze", "/tickets/blog-post"),
        ("/api/analyze/", "/tickets/blog-post/"),
        ("/api/analyze", "/tickets/blog-post"),
    ):
        u2 = u.replace(needle, repl)
        if u2 != u:
            return u2
    base = u.rstrip("/")
    if base.endswith("/tickets"):
        return f"{base}/blog-post/"
    return f"{base}/tickets/blog-post/"


def _default_author_name() -> str:
    return (getattr(settings, "BLOG_AUTHOR_NAME", None) or "Nyuydine Bill").strip()


def _estimate_read_minutes(body: str) -> int:
    words = len(re.findall(r"\w+", body or ""))
    return max(5, min(25, round(words / 200) or 5))


def _humanize_prose(text: str) -> str:
    """Strip em/en dashes from published copy (safety net after agent post-processing)."""
    if not text:
        return text
    cleaned = re.sub(r"\s*[—–]\s*", ", ", text)
    cleaned = re.sub(r",\s*,+", ", ", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    return cleaned.strip()


def _normalize_image_url(value: Any) -> Optional[str]:
    if value is None:
        return None
    url = str(value).strip()
    if not url or url.lower() in ("null", "none", "n/a"):
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return url[:500]


def _unique_slug(base_slug: str) -> str:
    slug = slugify(base_slug)[:200] or "blog-post"
    if not BlogPost.objects.filter(slug=slug).exists():
        return slug
    suffix = 2
    while BlogPost.objects.filter(slug=f"{slug}-{suffix}").exists():
        suffix += 1
    return f"{slug}-{suffix}"[:220]


def fetch_blog_draft_from_agent(*, target_date: date, recent_posts: List[Dict[str, str]]) -> Dict[str, Any]:
    """Call FastAPI ``POST /tickets/blog-post/`` and return parsed draft fields."""
    url = _agent_blog_post_url()
    payload = {
        "target_date": target_date.isoformat(),
        "author_name": _default_author_name(),
        "categories": list(_BLOG_CATEGORIES),
        "recent_posts": recent_posts[:40],
    }
    timeout = int(getattr(settings, "AI_AGENT_HTTP_TIMEOUT", 120))
    resp = requests.post(
        url,
        json=payload,
        headers=get_agent_service_headers(),
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Agent returned non-object JSON")
    return data


def create_blog_post_from_draft(draft: Dict[str, Any], *, target_date: date, is_ai_generated: bool = True) -> BlogPost:
    """Validate agent draft and persist a published BlogPost."""
    title = _humanize_prose(str(draft.get("title") or "").strip())
    body = _humanize_prose(str(draft.get("body") or "").strip())
    excerpt = _humanize_prose(str(draft.get("excerpt") or "").strip())
    category = str(draft.get("category") or "").strip() or "Best Practices"
    if not title or not body or not excerpt:
        raise ValueError("Draft missing title, body, or excerpt")

    slug_raw = str(draft.get("slug") or title).strip()
    slug = _unique_slug(slug_raw)

    read_minutes = draft.get("read_time_minutes")
    try:
        read_minutes = int(read_minutes)
    except (TypeError, ValueError):
        read_minutes = _estimate_read_minutes(body)
    read_minutes = max(5, min(25, read_minutes))

    image_url = _normalize_image_url(draft.get("image_url"))
    author_name = str(draft.get("author_name") or _default_author_name()).strip()

    return BlogPost.objects.create(
        slug=slug,
        title=title[:300],
        excerpt=excerpt[:2000],
        body=body,
        category=category[:100],
        read_time_minutes=read_minutes,
        image_url=image_url,
        author_name=author_name[:120],
        published_at=target_date,
        is_published=True,
        is_ai_generated=is_ai_generated,
    )


def blog_post_exists_for_date(target_date: date) -> bool:
    return BlogPost.objects.filter(published_at=target_date, is_ai_generated=True).exists()


def recent_posts_for_agent(limit: int = 30) -> List[Dict[str, str]]:
    rows = BlogPost.objects.filter(is_published=True).order_by("-published_at")[:limit]
    return [{"slug": p.slug, "title": p.title, "category": p.category} for p in rows]


def generate_daily_blog_post(*, force: bool = False) -> Optional[BlogPost]:
    """
    Generate one AI blog post for today (UTC date).
    Skips if an AI post already exists for today unless ``force=True``.
    """
    today = timezone.now().date()
    if not force and blog_post_exists_for_date(today):
        logger.info("Daily blog skipped: AI post already exists for %s", today)
        return None

    recent = recent_posts_for_agent()
    draft = fetch_blog_draft_from_agent(target_date=today, recent_posts=recent)
    post = create_blog_post_from_draft(draft, target_date=today, is_ai_generated=True)
    logger.info("Daily blog created slug=%s id=%s", post.slug, post.pk)
    return post
