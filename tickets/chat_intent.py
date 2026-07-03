"""
Lightweight chat intent helpers (no LLM) for follow-up messages.
"""
from __future__ import annotations

import re

_MAX_RESOLUTION_SUCCESS_LEN = 120

# Phrases that indicate the user is closing the loop after a successful fix.
_SUCCESS_PHRASES = (
    r"\b(?:it|that|this)\s+(?:has\s+)?worked\b",
    r"\b(?:has\s+)?worked(?:\s+for\s+me|\s+now|\s+perfectly|\s+fine)?\b",
    r"\b(?:it'?s\s+)?(?:fixed|sorted|resolved|good\s+now|all\s+good|fine\s+now|working\s+now|back\s+to\s+normal)\b",
    r"\b(?:problem\s+)?(?:is\s+)?(?:fixed|solved|gone|resolved|sorted)\b",
    r"\bthanks?(?:\s+you)?[,!.]?\s*(?:it\s+)?worked\b",
    r"\bthank\s+you[,!.]?\s*(?:it\s+)?(?:worked|fixed|sorted|resolved)\b",
)

_SUCCESS_RE = re.compile(
    "|".join(f"(?:{p})" for p in _SUCCESS_PHRASES),
    re.IGNORECASE,
)


def user_message_indicates_resolution_success(message: str) -> bool:
    """
    True when the user is confirming a fix worked (e.g. "it worked", "all good now").
    Ignores long messages to avoid false positives on new issues.
    """
    text = (message or "").strip()
    if not text or len(text) > _MAX_RESOLUTION_SUCCESS_LEN:
        return False
    if not _SUCCESS_RE.search(text):
        return False
    # Avoid "still doesn't work" / "worked before but …" style regressions.
    lowered = text.lower()
    if "doesn't work" in lowered or "does not work" in lowered or "still not" in lowered:
        return False
    if "worked before" in lowered or "used to work" in lowered:
        return False
    if " but " in lowered and any(
        w in lowered for w in ("broke", "again", "still", "not", "another", "else", "problem", "issue")
    ):
        return False
    return True
