"""Shared helpers for transient Postgres / Docker DNS failures."""
from __future__ import annotations

DNS_PATTERNS = (
    "could not translate host name",
    "name or service not known",
    "temporary failure in name resolution",
    "nodename nor servname provided",
)

TRANSIENT_DB_PATTERNS = (
    "connection refused",
    "server closed the connection unexpectedly",
    "ssl connection has been closed unexpectedly",
    "connection already closed",
    "terminating connection due to administrator command",
    "too many connections",
    "timeout expired",
    "could not connect to server",
)


def exception_text(exc: BaseException) -> str:
    return str(exc or "").lower()


def is_dns_resolution_error(exc: BaseException) -> bool:
    text = exception_text(exc)
    return any(p in text for p in DNS_PATTERNS)


def is_transient_db_error(exc: BaseException) -> bool:
    text = exception_text(exc)
    return is_dns_resolution_error(exc) or any(p in text for p in TRANSIENT_DB_PATTERNS)
