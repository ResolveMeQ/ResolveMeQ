"""SSRF guard for user-supplied outbound URLs (e.g. webhook endpoints).

Workspace owners can register arbitrary outbound webhook URLs. Without
validation, a malicious or compromised owner could point a webhook at the
cloud metadata endpoint (169.254.169.254), localhost, an internal service
DNS name, or an RFC1918 private address, and get the backend to make
requests on their behalf.

This module resolves the URL's hostname and rejects it if it (or any of
its resolved addresses) is loopback, link-local, private, reserved, or
otherwise non-public. Callers should run this check both when a URL is
first saved (create/update) and again immediately before delivery, since
DNS answers can change between the two (DNS rebinding).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeWebhookURLError(ValueError):
    """Raised when a webhook URL is not safe to deliver to."""


def _is_unsafe_ip(ip: "ipaddress._BaseAddress") -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_webhook_url(url: str) -> None:
    """Raise UnsafeWebhookURLError if ``url`` is unsafe to send requests to.

    Rejects non-http(s) schemes, missing hostnames, IP-literal hosts that
    are loopback/private/link-local/reserved/multicast, and hostnames that
    resolve (via DNS) to any such address.

    If DNS resolution fails outright (e.g. the host doesn't exist), we do
    not block: no request can be made to a name that doesn't resolve, so
    there is no SSRF exposure, and blocking here would also make the check
    brittle against transient DNS hiccups. The real HTTP request will fail
    on its own in that case.
    """
    if not url or not url.strip():
        raise UnsafeWebhookURLError("URL is required.")

    parsed = urlsplit(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeWebhookURLError("Webhook URL must use http or https.")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeWebhookURLError("Webhook URL must include a hostname.")

    # If the host is itself a literal IP address, check it directly.
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_unsafe_ip(literal_ip):
            raise UnsafeWebhookURLError(
                f"Webhook URL points to a disallowed address ({literal_ip})."
            )
        return

    # Otherwise resolve the hostname and check every address it maps to,
    # to guard against multi-A-record DNS rebinding tricks.
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError):
        return

    for info in addrinfo:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_unsafe_ip(ip):
            raise UnsafeWebhookURLError(
                f"Webhook URL hostname '{hostname}' resolves to a disallowed "
                f"address ({ip})."
            )
