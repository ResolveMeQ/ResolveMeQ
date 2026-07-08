"""Notify search engines after new public content is published."""
from __future__ import annotations

import logging
from urllib.parse import quote

import requests
from django.conf import settings

from base.public_seo import marketing_sitemap_url

logger = logging.getLogger(__name__)


def notify_search_engines_sitemap_updated() -> None:
    """
    Ping Bing (and legacy Google endpoint) so crawlers re-fetch the live sitemap sooner.
    Google primarily relies on Search Console + lastmod; this is a best-effort nudge.
    """
    if not getattr(settings, "ENABLE_SITEMAP_PING", True):
        return

    sitemap_url = marketing_sitemap_url()
    ping_targets = [
        f"https://www.bing.com/ping?sitemap={quote(sitemap_url, safe='')}",
        f"https://www.google.com/ping?sitemap={quote(sitemap_url, safe='')}",
    ]
    for url in ping_targets:
        try:
            resp = requests.get(url, timeout=15)
            logger.info("Sitemap ping %s → HTTP %s", url.split("?")[0], resp.status_code)
        except Exception as exc:
            logger.warning("Sitemap ping failed %s: %s", url.split("?")[0], exc)
