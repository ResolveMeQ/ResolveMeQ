"""Jira Cloud connector — create/update issues on escalate (P2-9)."""

from __future__ import annotations

import base64
import logging
from typing import Any, Optional, Tuple

from integrations.connectors.base import (
    ConnectorError,
    circuit_is_open,
    http_get_json,
    http_post_json,
    record_delivery_failure,
    record_delivery_success,
)

logger = logging.getLogger(__name__)


def normalize_site_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise ValueError("Jira site URL is required.")
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


def get_active_installation(team_id):
    from integrations.models import JiraInstallation

    if not team_id:
        return None
    return (
        JiraInstallation.objects.filter(resolvemeq_team_id=team_id, is_active=True)
        .order_by("-updated_at")
        .first()
    )


def _auth_header(installation) -> dict:
    token = base64.b64encode(
        f"{installation.user_email}:{installation.api_token}".encode()
    ).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _api_url(installation, path: str) -> str:
    base = normalize_site_url(installation.site_url)
    return f"{base}{path}"


def _jira_request(installation, method: str, path: str, *, body: bytes | None = None) -> Any:
    if circuit_is_open(installation):
        raise ConnectorError("Jira connector circuit open — try again later.")
    url = _api_url(installation, path)
    headers = _auth_header(installation)
    if method == "GET":
        response = http_get_json(url, headers=headers)
    else:
        response = http_post_json(url, body=body or b"{}", headers=headers)
    if response.status_code >= 400:
        record_delivery_failure(installation)
        detail = (response.text or "")[:500]
        raise ConnectorError(f"Jira API error (HTTP {response.status_code}): {detail}")
    record_delivery_success(installation)
    if response.status_code == 204 or not response.text:
        return {}
    return response.json()


def _plain_description(text: str) -> dict:
    """Jira Cloud API v3 ADF document from plain text."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text[:32000]}],
            }
        ],
    }


def build_issue_fields(installation, ticket) -> dict:
    summary = f"ResolveMeQ #{ticket.ticket_id}: {(ticket.issue_type or 'Support request')[:180]}"
    lines = [
        f"ResolveMeQ ticket #{ticket.ticket_id}",
        f"Category: {ticket.category or 'other'}",
        f"Priority: {ticket.escalation_priority or 'medium'}",
        "",
        ticket.description or "(no description)",
    ]
    return {
        "project": {"key": installation.project_key},
        "summary": summary[:255],
        "description": _plain_description("\n".join(lines)),
        "issuetype": {"name": installation.issue_type or "Task"},
    }


def create_issue_for_ticket(installation, ticket) -> Tuple[str, str]:
    import json

    payload = {"fields": build_issue_fields(installation, ticket)}
    data = _jira_request(
        installation,
        "POST",
        "/rest/api/3/issue",
        body=json.dumps(payload).encode("utf-8"),
    )
    key = data.get("key")
    if not key:
        raise ConnectorError("Jira did not return an issue key.")
    base = normalize_site_url(installation.site_url)
    url = f"{base}/browse/{key}"
    return key, url


def get_issue(installation, issue_key: str) -> Optional[dict]:
    try:
        return _jira_request(installation, "GET", f"/rest/api/3/issue/{issue_key}?fields=status")
    except ConnectorError:
        return None


def transition_issue(installation, issue_key: str, transition_name: str) -> bool:
    import json

    transitions = _jira_request(installation, "GET", f"/rest/api/3/issue/{issue_key}/transitions")
    target_id = None
    for tr in (transitions or {}).get("transitions") or []:
        if (tr.get("name") or "").lower() == (transition_name or "").lower():
            target_id = tr.get("id")
            break
    if not target_id:
        logger.warning("Jira transition %r not found for %s", transition_name, issue_key)
        return False
    _jira_request(
        installation,
        "POST",
        f"/rest/api/3/issue/{issue_key}/transitions",
        body=json.dumps({"transition": {"id": target_id}}).encode("utf-8"),
    )
    return True
