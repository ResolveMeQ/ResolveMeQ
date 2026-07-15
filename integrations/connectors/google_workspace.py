"""Google Workspace read connector — user exists, license SKU (P2-8)."""

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

VALID_GOOGLE_CHECKS = frozenset({"user_exists", "has_license"})
VALID_GOOGLE_ACTIONS = frozenset({"deactivate_user", "reset_password", "remove_from_group", "revoke_license"})

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DIRECTORY_API = "https://admin.googleapis.com/admin/directory/v1"
GOOGLE_LICENSING_API = "https://licensing.googleapis.com/apps/licensing/v1"


def get_active_installation(team_id):
    from integrations.models import GoogleWorkspaceInstallation

    if not team_id:
        return None
    return (
        GoogleWorkspaceInstallation.objects.filter(resolvemeq_team_id=team_id, is_active=True)
        .order_by("-updated_at")
        .first()
    )


def _token_expired(installation) -> bool:
    if not installation.token_expires_at:
        return False
    return installation.token_expires_at <= timezone.now() + timedelta(seconds=60)


def refresh_access_token(installation) -> None:
    if not installation.refresh_token:
        raise ConnectorError("Google refresh token missing — reconnect Google Workspace.")
    client_id = settings.GOOGLE_WORKSPACE_CLIENT_ID
    client_secret = settings.GOOGLE_WORKSPACE_CLIENT_SECRET
    if not client_id or not client_secret:
        raise ConnectorError("Google Workspace OAuth is not configured on the server.")

    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": installation.refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    response = http_post_json(
        GOOGLE_TOKEN_URL,
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Google token refresh failed (HTTP {response.status_code}).")
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
        raise ConnectorError("Google Workspace connector circuit open — try again later.")
    if not installation.access_token:
        raise ConnectorError("Google Workspace is not connected for this workspace.")
    if _token_expired(installation):
        refresh_access_token(installation)
    return installation.access_token


def google_api_get(installation, url: str) -> Any:
    token = _ensure_token(installation)
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
        raise ConnectorError(f"Google API error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json()


def google_api_patch(installation, url: str, body: dict) -> Any:
    token = _ensure_token(installation)
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
        raise ConnectorError(f"Google API error (HTTP {response.status_code}).")
    record_delivery_success(installation)
    return response.json() if response.content else {}


def google_api_delete(installation, url: str) -> None:
    token = _ensure_token(installation)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = http_delete_json(url, headers=headers)
    if response.status_code == 401:
        refresh_access_token(installation)
        headers["Authorization"] = f"Bearer {installation.access_token}"
        response = http_delete_json(url, headers=headers)
    if response.status_code >= 400:
        record_delivery_failure(installation)
        raise ConnectorError(f"Google API error (HTTP {response.status_code}).")
    record_delivery_success(installation)


def find_user_by_email(installation, email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    if not email:
        return None
    encoded = urllib.parse.quote(email, safe="")
    return google_api_get(installation, f"{GOOGLE_DIRECTORY_API}/users/{encoded}")


def user_exists_by_email(installation, email: str) -> Tuple[bool, str]:
    user = find_user_by_email(installation, email)
    if user:
        suspended = user.get("suspended", False)
        if suspended:
            return False, f"Google user exists but is suspended ({email})."
        return True, f"Google Workspace user found ({email})."
    return False, f"No Google Workspace user with email {email}."


def user_has_license(installation, email: str, sku_id: str) -> Tuple[bool, str]:
    sku_id = (sku_id or "").strip()
    if not sku_id:
        return False, "sku_id is required for has_license check."
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Google Workspace user with email {email}."
    encoded_email = urllib.parse.quote(email, safe="")
    encoded_sku = urllib.parse.quote(sku_id, safe="")
    license_data = google_api_get(
        installation,
        f"{GOOGLE_LICENSING_API}/product/Google-Apps/sku/{encoded_sku}/user/{encoded_email}",
    )
    if license_data:
        state = license_data.get("state") or "ACTIVE"
        return True, f"Google license {sku_id} assigned ({state})."
    return False, f"User does not have Google license SKU {sku_id}."


def run_google_check(
    installation,
    check: str,
    *,
    email: str,
    sku_id: str = "",
) -> Tuple[bool, str, dict]:
    check = (check or "").strip()
    if check not in VALID_GOOGLE_CHECKS:
        return False, f"Unknown Google check: {check}", {}
    if check == "user_exists":
        ok, msg = user_exists_by_email(installation, email)
        return ok, msg, {"email": email}
    ok, msg = user_has_license(installation, email, sku_id)
    return ok, msg, {"email": email, "sku_id": sku_id}


def deactivate_user(installation, email: str) -> Tuple[bool, str, dict]:
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Google Workspace user with email {email}.", {"email": email}
    encoded = urllib.parse.quote(email, safe="")
    google_api_patch(installation, f"{GOOGLE_DIRECTORY_API}/users/{encoded}", {"suspended": True})
    return True, f"Google Workspace user {email} suspended.", {"email": email}


def reset_password(installation, email: str) -> Tuple[bool, str, dict]:
    user = find_user_by_email(installation, email)
    if not user:
        return False, f"No Google Workspace user with email {email}.", {"email": email}
    temp_password = generate_temp_password()
    encoded = urllib.parse.quote(email, safe="")
    google_api_patch(
        installation,
        f"{GOOGLE_DIRECTORY_API}/users/{encoded}",
        {"password": temp_password, "changePasswordAtNextLogin": True},
    )
    return True, f"Password reset for Google Workspace user {email}.", {"email": email, "temp_password": temp_password}


def remove_from_group(installation, email: str, group_id: str) -> Tuple[bool, str, dict]:
    group_id = (group_id or "").strip()
    if not group_id:
        return False, "group_id is required for remove_from_group.", {"email": email}
    encoded_group = urllib.parse.quote(group_id, safe="")
    encoded_member = urllib.parse.quote(email, safe="")
    google_api_delete(installation, f"{GOOGLE_DIRECTORY_API}/groups/{encoded_group}/members/{encoded_member}")
    return True, f"Google Workspace user {email} removed from group {group_id}.", {"email": email, "group_id": group_id}


def revoke_license(installation, email: str, sku_id: str) -> Tuple[bool, str, dict]:
    sku_id = (sku_id or "").strip()
    if not sku_id:
        return False, "sku_id is required for revoke_license.", {"email": email}
    encoded_email = urllib.parse.quote(email, safe="")
    encoded_sku = urllib.parse.quote(sku_id, safe="")
    google_api_delete(
        installation,
        f"{GOOGLE_LICENSING_API}/product/Google-Apps/sku/{encoded_sku}/user/{encoded_email}",
    )
    return True, f"Google license {sku_id} revoked for {email}.", {"email": email, "sku_id": sku_id}


def run_google_action(
    installation,
    action: str,
    *,
    email: str,
    group_id: str = "",
    sku_id: str = "",
) -> Tuple[bool, str, dict]:
    action = (action or "").strip()
    if action not in VALID_GOOGLE_ACTIONS:
        return False, f"Unknown Google action: {action}", {}
    if action == "deactivate_user":
        return deactivate_user(installation, email)
    if action == "reset_password":
        return reset_password(installation, email)
    if action == "remove_from_group":
        return remove_from_group(installation, email, group_id)
    return revoke_license(installation, email, sku_id)
