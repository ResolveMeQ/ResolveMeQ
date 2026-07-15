"""Okta read connector — OAuth, user lookup, group membership (P2-7)."""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from integrations.connectors.base import (
    ConnectorError,
    circuit_is_open,
    http_delete_json,
    http_get_json,
    http_post_json,
    record_delivery_failure,
    record_delivery_success,
)

logger = logging.getLogger(__name__)

VALID_OKTA_CHECKS = frozenset({"user_exists", "group_member"})
VALID_OKTA_ACTIONS = frozenset({"deactivate_user", "reset_password", "remove_from_group"})


def normalize_okta_domain(raw: str) -> str:
    domain = (raw or "").strip().lower()
    domain = domain.replace("https://", "").replace("http://", "")
    if domain.endswith(".okta.com"):
        domain = domain[: -len(".okta.com")]
    domain = domain.split("/")[0].strip(".")
    if not domain:
        raise ValueError("Okta domain is required.")
    return domain


def issuer_for_domain(domain: str) -> str:
    d = normalize_okta_domain(domain)
    return f"https://{d}.okta.com/oauth2/default"


def org_base_url(domain: str) -> str:
    d = normalize_okta_domain(domain)
    return f"https://{d}.okta.com"


def get_active_installation(team_id) -> Optional["OktaInstallation"]:
    from integrations.models import OktaInstallation

    if not team_id:
        return None
    return (
        OktaInstallation.objects.filter(resolvemeq_team_id=team_id, is_active=True)
        .order_by("-updated_at")
        .first()
    )


def _token_expired(installation) -> bool:
    if not installation.token_expires_at:
        return False
    return installation.token_expires_at <= timezone.now() + timedelta(seconds=60)


def refresh_access_token(installation) -> None:
    if not installation.refresh_token:
        raise ConnectorError("Okta refresh token missing — reconnect Okta.")
    client_id = settings.OKTA_CLIENT_ID
    client_secret = settings.OKTA_CLIENT_SECRET
    if not client_id or not client_secret:
        raise ConnectorError("Okta OAuth is not configured on the server.")

    token_url = f"{installation.issuer_url.rstrip('/')}/v1/token"
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": installation.refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    response = http_post_json(
        token_url,
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Okta token refresh failed (HTTP {response.status_code}).")
    data = response.json()
    installation.access_token = data.get("access_token") or installation.access_token
    if data.get("refresh_token"):
        installation.refresh_token = data["refresh_token"]
    expires_in = data.get("expires_in")
    if expires_in:
        installation.token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
    installation.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
    record_delivery_success(installation)


def _ensure_token(installation) -> str:
    if circuit_is_open(installation):
        raise ConnectorError("Okta connector circuit open — try again later.")
    if not installation.access_token:
        raise ConnectorError("Okta is not connected for this workspace.")
    if _token_expired(installation):
        refresh_access_token(installation)
    return installation.access_token


def okta_api_get(installation, path: str, *, params: Optional[dict] = None) -> Any:
    token = _ensure_token(installation)
    base = org_base_url(installation.okta_domain)
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    response = http_get_json(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    if response.status_code == 401:
        refresh_access_token(installation)
        token = installation.access_token
        response = http_get_json(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Okta API error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json()


def okta_api_post(installation, path: str, body: Optional[dict] = None) -> Any:
    token = _ensure_token(installation)
    base = org_base_url(installation.okta_domain)
    url = f"{base}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = json.dumps(body or {}).encode("utf-8")
    response = http_post_json(url, body=payload, headers=headers)
    if response.status_code == 401:
        refresh_access_token(installation)
        headers["Authorization"] = f"Bearer {installation.access_token}"
        response = http_post_json(url, body=payload, headers=headers)
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Okta API error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json() if response.content else {}


def okta_api_delete(installation, path: str) -> None:
    token = _ensure_token(installation)
    base = org_base_url(installation.okta_domain)
    url = f"{base}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = http_delete_json(url, headers=headers)
    if response.status_code == 401:
        refresh_access_token(installation)
        headers["Authorization"] = f"Bearer {installation.access_token}"
        response = http_delete_json(url, headers=headers)
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Okta API error (HTTP {response.status_code}).")
    record_delivery_success(installation)


def find_user_by_email(installation, email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    if not email:
        return None
    query = urllib.parse.quote(f'profile.email eq "{email}"')
    users = okta_api_get(installation, f"/api/v1/users?search={query}&limit=1")
    if isinstance(users, list) and users:
        return users[0]
    return None


def user_exists_by_email(installation, email: str) -> Tuple[bool, str]:
    user = find_user_by_email(installation, email)
    if user:
        status = (user.get("status") or "UNKNOWN").upper()
        return True, f"Okta user found ({status})."
    return False, f"No Okta user with email {email}."


def user_in_group(installation, email: str, group_id: str) -> Tuple[bool, str]:
    group_id = (group_id or "").strip()
    if not group_id:
        return False, "group_id is required for group_member check."
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Okta user with email {email}."
    user_id = user.get("id")
    groups = okta_api_get(installation, f"/api/v1/users/{user_id}/groups")
    if not isinstance(groups, list):
        return False, "Unexpected Okta groups response."
    for group in groups:
        if group.get("id") == group_id:
            name = group.get("profile", {}).get("name") or group_id
            return True, f"User is in group {name}."
    return False, f"User is not in group {group_id}."


def run_okta_check(installation, check: str, *, email: str, group_id: str = "") -> Tuple[bool, str, dict]:
    check = (check or "").strip()
    if check not in VALID_OKTA_CHECKS:
        return False, f"Unknown Okta check: {check}", {}
    if check == "user_exists":
        ok, msg = user_exists_by_email(installation, email)
        return ok, msg, {"email": email}
    ok, msg = user_in_group(installation, email, group_id)
    return ok, msg, {"email": email, "group_id": group_id}


def deactivate_user(installation, email: str) -> Tuple[bool, str, dict]:
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Okta user with email {email}.", {"email": email}
    user_id = user.get("id")
    okta_api_post(installation, f"/api/v1/users/{user_id}/lifecycle/deactivate")
    return True, f"Okta user {email} deactivated.", {"email": email, "user_id": user_id}


def reset_password(installation, email: str) -> Tuple[bool, str, dict]:
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Okta user with email {email}.", {"email": email}
    user_id = user.get("id")
    okta_api_post(installation, f"/api/v1/users/{user_id}/lifecycle/reset_password?sendEmail=true")
    return True, f"Password reset email sent to Okta user {email}.", {"email": email, "user_id": user_id}


def remove_from_group(installation, email: str, group_id: str) -> Tuple[bool, str, dict]:
    group_id = (group_id or "").strip()
    if not group_id:
        return False, "group_id is required for remove_from_group.", {"email": email}
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Okta user with email {email}.", {"email": email}
    user_id = user.get("id")
    okta_api_delete(installation, f"/api/v1/groups/{group_id}/users/{user_id}")
    return True, f"Okta user {email} removed from group {group_id}.", {"email": email, "user_id": user_id, "group_id": group_id}


def run_okta_action(installation, action: str, *, email: str, group_id: str = "") -> Tuple[bool, str, dict]:
    action = (action or "").strip()
    if action not in VALID_OKTA_ACTIONS:
        return False, f"Unknown Okta action: {action}", {}
    if action == "deactivate_user":
        return deactivate_user(installation, email)
    if action == "reset_password":
        return reset_password(installation, email)
    return remove_from_group(installation, email, group_id)
