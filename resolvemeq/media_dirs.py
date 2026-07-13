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
