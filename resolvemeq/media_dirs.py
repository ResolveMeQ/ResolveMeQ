"""Ensure writable upload subdirectories under MEDIA_ROOT."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Subdirs created eagerly so default_storage.save() does not fail on first upload.
MEDIA_SUBDIRS = (
    "ticket_pending",
    "kb_community",
    "profiles",
)


def absolute_media_url(relative_path: str, request=None) -> str:
    """
    Build a browser-loadable URL for a file stored under MEDIA_ROOT.

    Prefer API_BASE_URL so production links use https://api… even when the
    upstream request arrived as http behind a proxy.
    """
    from django.conf import settings

    rel = (relative_path or "").lstrip("/")
    if rel.startswith("http://") or rel.startswith("https://"):
        return rel

    media_prefix = (settings.MEDIA_URL or "/media/").strip("/")
    path = f"/{media_prefix}/{rel}".replace("//", "/")
    base = (getattr(settings, "API_BASE_URL", None) or "").rstrip("/")
    if base:
        return f"{base}{path}"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def ensure_media_subdirectories(media_root: str | os.PathLike | None = None) -> None:
    """
    Create standard upload folders under MEDIA_ROOT.

    Raises PermissionError if the volume is not writable (e.g. root-owned Docker volume).
    """
    from django.conf import settings

    root = Path(media_root or settings.MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    for name in MEDIA_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
