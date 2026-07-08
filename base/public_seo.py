"""Live SEO feeds (sitemap, RSS) generated from the database on every request."""
from __future__ import annotations

import os
from datetime import date, datetime, timezone as dt_timezone
from email.utils import format_datetime
from typing import List, Optional, Tuple
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.utils import timezone
from django.utils.text import slugify


def _request_host(request) -> str:
    """Host header without raising DisallowedHost (safe for tests and proxies)."""
    if request is None:
        return ""
    try:
        return (request.get_host() or "").lower()
    except DisallowedHost:
        return (request.META.get("HTTP_HOST") or "").lower()


def get_public_site_urls(request) -> Tuple[str, str]:
    """
    Canonical public domains for sitemap/RSS links.
    - marketing: resolvemeq.net (journal, landing pages)
    - app: app.resolvemeq.net (KB, community)
    """
    default_app = "https://app.resolvemeq.net"
    default_marketing = "https://resolvemeq.net"

    app_base = (getattr(settings, "PUBLIC_APP_URL", "") or default_app).rstrip("/")
    marketing_base = (getattr(settings, "PUBLIC_MARKETING_URL", "") or default_marketing).rstrip("/")

    if request is None:
        return app_base, marketing_base

    # Production/staging: when PUBLIC_* are set in the environment, never derive from Host.
    if os.getenv("PUBLIC_APP_URL", "").strip() or os.getenv("PUBLIC_MARKETING_URL", "").strip():
        return app_base, marketing_base

    host = _request_host(request)
    if "localhost" in host or "127.0.0.1" in host:
        app_base = request.build_absolute_uri("/").rstrip("/")
        marketing_base = request.build_absolute_uri("/").rstrip("/")

    return app_base, marketing_base


def marketing_sitemap_url() -> str:
    """Absolute sitemap URL crawlers should fetch (marketing domain)."""
    base = (getattr(settings, "PUBLIC_MARKETING_URL", "") or "https://resolvemeq.net").rstrip("/")
    return f"{base}/sitemap.xml"


_MARKETING_SECTIONS = (
    "features",
    "solutions",
    "workflow",
    "pricing",
    "faq",
    "contact",
    "newsletter",
)

_MARKETING_LEGAL = ("privacy", "terms", "cookies")


def _iso_lastmod(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10]


def _sitemap_entry(
    loc: str,
    *,
    lastmod: Optional[str] = None,
    changefreq: Optional[str] = None,
    priority: Optional[str] = None,
) -> str:
    parts = [f"  <url><loc>{escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"<lastmod>{escape(lastmod)}</lastmod>")
    if changefreq:
        parts.append(f"<changefreq>{changefreq}</changefreq>")
    if priority:
        parts.append(f"<priority>{priority}</priority>")
    parts.append("</url>")
    return "".join(parts)


def build_sitemap_url_lines(app_base: str, marketing_base: str) -> List[str]:
    """Query DB and return sitemap <url> lines (marketing + app public content)."""
    from base.models import BlogPost
    from knowledge_base.models import KBQuestion, KnowledgeBaseArticle

    today = timezone.now().date().isoformat()
    lines: List[str] = []

    lines.append(_sitemap_entry(f"{marketing_base}/", lastmod=today, changefreq="weekly", priority="1.0"))
    for section in _MARKETING_SECTIONS:
        lines.append(
            _sitemap_entry(
                f"{marketing_base}/{section}",
                lastmod=today,
                changefreq="weekly",
                priority="0.9",
            )
        )
    lines.append(
        _sitemap_entry(f"{marketing_base}/blog", lastmod=today, changefreq="daily", priority="0.85")
    )

    for post in BlogPost.objects.filter(is_published=True).order_by("-published_at"):
        lastmod = _iso_lastmod(post.updated_at) or _iso_lastmod(post.published_at) or today
        lines.append(
            _sitemap_entry(
                f"{marketing_base}/blog/{post.slug}",
                lastmod=lastmod,
                changefreq="weekly",
                priority="0.75",
            )
        )

    for legal in _MARKETING_LEGAL:
        lines.append(
            _sitemap_entry(f"{marketing_base}/{legal}", lastmod=today, changefreq="monthly", priority="0.7")
        )

    lines.append(_sitemap_entry(f"{app_base}/knowledge-base", lastmod=today, changefreq="daily", priority="0.8"))
    lines.append(
        _sitemap_entry(f"{app_base}/knowledge-base?view=community", lastmod=today, changefreq="daily", priority="0.8")
    )

    # Platform/global KB only — team-scoped articles are not public index targets.
    for article in (
        KnowledgeBaseArticle.objects.filter(is_published=True, team__isnull=True)
        .order_by("-updated_at")[:5000]
    ):
        article_slug = slugify(article.title)[:120] or "article"
        loc = f"{app_base}/knowledge-base/article/{article_slug}~{article.kb_id}"
        lastmod = _iso_lastmod(article.updated_at)
        lines.append(_sitemap_entry(loc, lastmod=lastmod, changefreq="weekly", priority="0.7"))

    for question in KBQuestion.objects.filter(is_published=True).order_by("-updated_at")[:5000]:
        q_slug = slugify(question.title)[:120] or f"question-{question.id}"
        loc = f"{app_base}/community/q/{q_slug}-{question.id}"
        lastmod = _iso_lastmod(question.updated_at)
        lines.append(_sitemap_entry(loc, lastmod=lastmod, changefreq="weekly", priority="0.65"))

    return lines


def render_sitemap_xml(app_base: str, marketing_base: str) -> str:
    lines = build_sitemap_url_lines(app_base, marketing_base)
    body = "\n".join(lines)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _pub_date_rss(iso_date: str) -> str:
    if not iso_date:
        return format_datetime(datetime.now(dt_timezone.utc))
    dt = datetime.strptime(iso_date[:10], "%Y-%m-%d").replace(tzinfo=dt_timezone.utc, hour=12)
    return format_datetime(dt)


def render_blog_rss_xml(marketing_base: str) -> str:
    from base.models import BlogPost

    author_default = getattr(settings, "BLOG_AUTHOR_NAME", "Nyuydine Bill")
    posts = BlogPost.objects.filter(is_published=True).order_by("-published_at", "-created_at")[:100]

    items = []
    for post in posts:
        link = f"{marketing_base}/blog/{post.slug}"
        pub = _pub_date_rss(_iso_lastmod(post.published_at) or "")
        author = (post.author_name or author_default).strip()
        items.append(
            "\n".join(
                [
                    "    <item>",
                    f"      <title>{escape(post.title)}</title>",
                    f"      <link>{escape(link)}</link>",
                    f'      <guid isPermaLink="true">{escape(link)}</guid>',
                    f"      <pubDate>{escape(pub)}</pubDate>",
                    f"      <description>{escape(post.excerpt)}</description>",
                    f"      <dc:creator>{escape(author)}</dc:creator>",
                    "    </item>",
                ]
            )
        )

    build_date = format_datetime(datetime.now(dt_timezone.utc))
    channel_link = f"{marketing_base}/blog"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Resolve Me Quickly — Journal</title>
    <link>{escape(channel_link)}</link>
    <description>Product notes, IT operations, and support automation from ResolveMeQ.</description>
    <language>en-us</language>
    <lastBuildDate>{escape(build_date)}</lastBuildDate>
    <atom:link href="{escape(f"{marketing_base}/rss.xml")}" rel="self" type="application/rss+xml" />
{chr(10).join(items)}
  </channel>
</rss>
"""


def render_app_robots_txt(app_base: str, marketing_base: str) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /knowledge-base",
            "Allow: /community/",
            "Disallow: /api/",
            f"Sitemap: {marketing_base}/sitemap.xml",
        ]
    )


def render_api_robots_txt() -> str:
    return "\n".join(["User-agent: *", "Disallow: /"])
