"""Logging filters for production noise control."""
from __future__ import annotations

import logging
import threading
import time

# Transient Postgres / Docker DNS failures that flood ADMINS when a poll endpoint retries.
_DNS_PATTERNS = (
    "could not translate host name",
    "name or service not known",
    "temporary failure in name resolution",
    "nodename nor servname provided",
)

_TRANSIENT_DB_PATTERNS = (
    "connection refused",
    "server closed the connection unexpectedly",
    "ssl connection has been closed unexpectedly",
    "connection already closed",
    "terminating connection due to administrator command",
    "too many connections",
    "timeout expired",
    "could not connect to server",
)


class SuppressTransientDbAdminEmailFilter(logging.Filter):
    """
    Keep console logs, but stop AdminEmailHandler from emailing every transient DB blip.

    DNS resolution failures for Supabase/pooler are suppressed entirely (Docker DNS flaps).
    Other transient OperationalError-style messages are rate-limited (one email / window).
    """

    def __init__(self, name: str = "", rate_limit_seconds: int = 3600):
        super().__init__(name)
        self.rate_limit_seconds = max(60, int(rate_limit_seconds or 3600))
        self._lock = threading.Lock()
        self._last_sent_at = 0.0

    def filter(self, record: logging.LogRecord) -> bool:
        text = self._record_text(record).lower()
        if any(p in text for p in _DNS_PATTERNS):
            return False
        if any(p in text for p in _TRANSIENT_DB_PATTERNS):
            return self._allow_rate_limited()
        return True

    def _allow_rate_limited(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_sent_at < self.rate_limit_seconds:
                return False
            self._last_sent_at = now
            return True

    @staticmethod
    def _record_text(record: logging.LogRecord) -> str:
        parts = [str(record.getMessage())]
        if record.exc_info and record.exc_info[1] is not None:
            parts.append(str(record.exc_info[1]))
        return " ".join(parts)
