"""Microsoft 365 read connector — user exists, license SKU (P2-8)."""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import timedelta
from typing import Any, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from integrations.connectors.base import (
    ConnectorError,
    circuit_is_open,
    generate_temp_password,
    http_delete_json,
    http_get_json,
    http_patch_json,
    http_post_json,
    record_delivery_failure,
    record_delivery_success,
)

logger = logging.getLogger(__name__)

VALID_MICROSOFT_CHECKS = frozenset({"user_exists", "has_license"})
VALID_MICROSOFT_ACTIONS = frozenset({"deactivate_user", "reset_password", "remove_from_group", "revoke_license"})

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_active_installation(team_id):
    from integrations.models import Microsoft365Installation

    if not team_id:
        return None
    return (
        Microsoft365Installation.objects.filter(resolvemeq_team_id=team_id, is_active=True)
        .order_by("-updated_at")
        .first()
    )


def _token_expired(installation) -> bool:
    if not installation.token_expires_at:
        return False
    return installation.token_expires_at <= timezone.now() + timedelta(seconds=60)


def _token_url(tenant_id: str = "common") -> str:
    return f"https://login.microsoftonline.com/{tenant_id or 'common'}/oauth2/v2.0/token"


def refresh_access_token(installation) -> None:
    if not installation.refresh_token:
        raise ConnectorError("Microsoft 365 refresh token missing — reconnect M365.")
    client_id = settings.MICROSOFT365_CLIENT_ID
    client_secret = settings.MICROSOFT365_CLIENT_SECRET
    if not client_id or not client_secret:
        raise ConnectorError("Microsoft 365 OAuth is not configured on the server.")

    tenant = installation.tenant_id or "common"
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": installation.refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": settings.MICROSOFT365_SCOPES,
    }).encode("utf-8")
    response = http_post_json(
        _token_url(tenant),
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Microsoft token refresh failed (HTTP {response.status_code}).")
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
        raise ConnectorError("Microsoft 365 connector circuit open — try again later.")
    if not installation.access_token:
        raise ConnectorError("Microsoft 365 is not connected for this workspace.")
    if _token_expired(installation):
        refresh_access_token(installation)
    return installation.access_token


def graph_api_get(installation, path: str) -> Any:
    token = _ensure_token(installation)
    url = f"{GRAPH_BASE}{path}"
    response = http_get_json(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if response.status_code == 401:
        refresh_access_token(installation)
        response = http_get_json(
            url,
            headers={"Authorization": f"Bearer {installation.access_token}", "Accept": "application/json"},
        )
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Microsoft Graph error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json()


def graph_api_patch(installation, path: str, body: dict) -> Any:
    token = _ensure_token(installation)
    url = f"{GRAPH_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = json.dumps(body).encode("utf-8")
    response = http_patch_json(url, body=payload, headers=headers)
    if response.status_code == 401:
        refresh_access_token(installation)
        headers["Authorization"] = f"Bearer {installation.access_token}"
        response = http_patch_json(url, body=payload, headers=headers)
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Microsoft Graph error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json() if response.content else {}


def graph_api_post(installation, path: str, body: Optional[dict] = None) -> Any:
    token = _ensure_token(installation)
    url = f"{GRAPH_BASE}{path}"
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
        raise ConnectorError(f"Microsoft Graph error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json() if response.content else {}


def graph_api_delete(installation, path: str) -> None:
    token = _ensure_token(installation)
    url = f"{GRAPH_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = http_delete_json(url, headers=headers)
    if response.status_code == 401:
        refresh_access_token(installation)
        headers["Authorization"] = f"Bearer {installation.access_token}"
        response = http_delete_json(url, headers=headers)
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Microsoft Graph error (HTTP {response.status_code}).")
    record_delivery_success(installation)


def find_user_by_email(installation, email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    if not email:
        return None
    encoded = urllib.parse.quote(email, safe="")
    return graph_api_get(installation, f"/users/{encoded}")


def user_exists_by_email(installation, email: str) -> Tuple[bool, str]:
    user = find_user_by_email(installation, email)
    if user:
        disabled = user.get("accountEnabled") is False
        if disabled:
            return False, f"Microsoft user exists but account is disabled ({email})."
        return True, f"Microsoft 365 user found ({email})."
    return False, f"No Microsoft 365 user with email {email}."


def user_has_license(installation, email: str, sku_id: str) -> Tuple[bool, str]:
    sku_id = (sku_id or "").strip()
    if not sku_id:
        return False, "sku_id is required for has_license check."
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Microsoft 365 user with email {email}."
    user_id = user.get("id")
    licenses = graph_api_get(installation, f"/users/{user_id}/licenseDetails")
    items = (licenses or {}).get("value") or []
    sku_upper = sku_id.upper()
    for lic in items:
        part = (lic.get("skuPartNumber") or "").upper()
        sku = str(lic.get("skuId") or "")
        if sku_upper == part or sku_id == sku:
            return True, f"Microsoft license {part or sku_id} assigned."
    return False, f"User does not have Microsoft license SKU {sku_id}."


def run_microsoft_check(
    installation,
    check: str,
    *,
    email: str,
    sku_id: str = "",
) -> Tuple[bool, str, dict]:
    check = (check or "").strip()
    if check not in VALID_MICROSOFT_CHECKS:
        return False, f"Unknown Microsoft check: {check}", {}
    if check == "user_exists":
        ok, msg = user_exists_by_email(installation, email)
        return ok, msg, {"email": email}
    ok, msg = user_has_license(installation, email, sku_id)
    return ok, msg, {"email": email, "sku_id": sku_id}


def deactivate_user(installation, email: str) -> Tuple[bool, str, dict]:
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Microsoft 365 user with email {email}.", {"email": email}
    user_id = user.get("id")
    graph_api_patch(installation, f"/users/{user_id}", {"accountEnabled": False})
    return True, f"Microsoft 365 user {email} account disabled.", {"email": email, "user_id": user_id}


def reset_password(installation, email: str) -> Tuple[bool, str, dict]:
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Microsoft 365 user with email {email}.", {"email": email}
    user_id = user.get("id")
    temp_password = generate_temp_password()
    graph_api_patch(
        installation,
        f"/users/{user_id}",
        {"passwordProfile": {"forceChangePasswordNextSignIn": True, "password": temp_password}},
    )
    return True, f"Password reset for Microsoft 365 user {email}.", {
        "email": email,
        "user_id": user_id,
        "temp_password": temp_password,
    }


def remove_from_group(installation, email: str, group_id: str) -> Tuple[bool, str, dict]:
    group_id = (group_id or "").strip()
    if not group_id:
        return False, "group_id is required for remove_from_group.", {"email": email}
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Microsoft 365 user with email {email}.", {"email": email}
    user_id = user.get("id")
    graph_api_delete(installation, f"/groups/{group_id}/members/{user_id}/$ref")
    return True, f"Microsoft 365 user {email} removed from group {group_id}.", {
        "email": email,
        "user_id": user_id,
        "group_id": group_id,
    }


def revoke_license(installation, email: str, sku_id: str) -> Tuple[bool, str, dict]:
    sku_id = (sku_id or "").strip()
    if not sku_id:
        return False, "sku_id is required for revoke_license.", {"email": email}
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Microsoft 365 user with email {email}.", {"email": email}
    user_id = user.get("id")
    graph_api_post(installation, f"/users/{user_id}/assignLicense", {"addLicenses": [], "removeLicenses": [sku_id]})
    return True, f"Microsoft license {sku_id} revoked for {email}.", {
        "email": email,
        "user_id": user_id,
        "sku_id": sku_id,
    }


def run_microsoft_action(
    installation,
    action: str,
    *,
    email: str,
    group_id: str = "",
    sku_id: str = "",
) -> Tuple[bool, str, dict]:
    action = (action or "").strip()
    if action not in VALID_MICROSOFT_ACTIONS:
        return False, f"Unknown Microsoft action: {action}", {}
    if action == "deactivate_user":
        return deactivate_user(installation, email)
    if action == "reset_password":
        return reset_password(installation, email)
    if action == "remove_from_group":
        return remove_from_group(installation, email, group_id)
    return revoke_license(installation, email, sku_id)
