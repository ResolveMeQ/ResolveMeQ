"""
Microsoft Teams bot: app-token acquisition, installation/conversation lookup, API helper.

Mirrors integrations/slack_installation.py's responsibilities. Key differences from Slack,
see the Teams integration plan for the full reasoning:
- Auth is OAuth2 client-credentials (bot-wide token), not a per-installation token like
  Slack's xoxb- bot token -- the bearer token here is the SAME for every tenant/team, only
  the (service_url, conversation_id) pair addresses a specific destination.
- Proactive DMs need a "conversation reference" resolved via the Bot Framework Connector
  REST API, not a single conversations.open call.
- No shadow-user fallback: Teams/AAD identities reliably carry a real email, so we map to
  an existing User by email first and only create one if no match exists.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

from base.models import User
from integrations.connectors.base import should_retry
from integrations.models import TeamsInstallation


def _request_with_retry(method: str, url: str, *, retry_delay: float = 1.0, **kwargs) -> requests.Response | None:
    """One retry on a transient failure (network error, 5xx, 429) -- mirrors
    slack_installation.py's helper; Teams has no persisted circuit breaker either."""
    for attempt in range(2):
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            if attempt == 0:
                time.sleep(retry_delay)
                continue
            logger.warning("Teams API %s %s failed: %s", method, url, exc)
            return None
        if attempt == 0 and should_retry(resp.status_code):
            time.sleep(retry_delay)
            continue
        return resp
    return None


logger = logging.getLogger(__name__)

_APP_TOKEN_CACHE_KEY = "teams_app_access_token"
_APP_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
_APP_TOKEN_SCOPE = "https://api.botframework.com/.default"


def get_app_access_token() -> str | None:
    """
    Bot-wide bearer token (client-credentials grant). Cached in the shared Django cache
    (Redis) so gunicorn/Celery worker processes don't each fetch their own copy -- this is
    the SAME token for every tenant/team, unlike Slack's per-installation bot token.
    """
    cached = cache.get(_APP_TOKEN_CACHE_KEY)
    if cached:
        return cached

    app_id = getattr(settings, "TEAMS_APP_ID", "") or ""
    app_password = getattr(settings, "TEAMS_APP_PASSWORD", "") or ""
    if not app_id or not app_password:
        return None

    try:
        resp = requests.post(
            _APP_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": app_id,
                "client_secret": app_password,
                "scope": _APP_TOKEN_SCOPE,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Teams app token fetch failed: %s", exc)
        return None

    token = data.get("access_token")
    expires_in = data.get("expires_in")
    if not token:
        return None
    try:
        ttl = max(60, int(expires_in) - 300)  # refresh 5 min before real expiry
    except (TypeError, ValueError):
        ttl = 1800
    cache.set(_APP_TOKEN_CACHE_KEY, token, timeout=ttl)
    return token


def get_installation_for_ticket(ticket) -> TeamsInstallation | None:
    team = getattr(ticket, "team", None)
    if team is None:
        return None
    return (
        TeamsInstallation.objects.filter(resolvemeq_team=team, is_active=True)
        .select_related("resolvemeq_team", "installed_by")
        .order_by("-updated_at")
        .first()
    )


def escalation_conversation_for_team(team) -> tuple[str, str] | None:
    """(service_url, conversation_id) for this team's escalation-channel post, if connected."""
    if team is None:
        return None
    inst = (
        TeamsInstallation.objects.filter(resolvemeq_team=team, is_active=True)
        .exclude(conversation_id="")
        .exclude(service_url="")
        .order_by("-updated_at")
        .first()
    )
    if not inst:
        return None
    return inst.service_url, inst.conversation_id


def display_name_for_teams_user(user) -> str:
    if not user:
        return ""
    name = (user.get_full_name() if hasattr(user, "get_full_name") else "") or ""
    name = name.strip()
    if name:
        return name
    return (
        (getattr(user, "username", None) or "").strip()
        or (getattr(user, "email", None) or "").strip()
        or "Member"
    )


def get_or_link_teams_user(
    aad_object_id: str,
    tenant_id: str,
    *,
    email: str | None = None,
    display_name: str | None = None,
) -> User:
    """
    Resolve to an existing ResolveMeQ User by email when possible (Teams/AAD identities
    reliably carry a real email), otherwise create one. Always links Profile.teams_*
    fields for future lookups, mirroring get_or_create_slack_shadow_user's profile-linking
    half but without a shadow-user-by-default fallback.
    """
    from base.models import Profile

    aad_object_id = (aad_object_id or "").strip()
    email_norm = (email or "").strip().lower()

    user = None
    if email_norm:
        user = User.objects.filter(email__iexact=email_norm).first()
    if user is None and aad_object_id:
        user = User.objects.filter(profile__teams_aad_object_id=aad_object_id).first()

    if user is None:
        if not email_norm:
            email_norm = f"{aad_object_id or 'unknown'}@teams.local"
        username = aad_object_id or email_norm.split("@", 1)[0]
        user, created = User.objects.get_or_create(
            email=email_norm,
            defaults={"username": username[:150], "is_active": True, "is_verified": False},
        )
        if created:
            user.set_unusable_password()
            if display_name and not (user.first_name or user.last_name):
                parts = display_name.strip().split(" ", 1)
                user.first_name = parts[0]
                user.last_name = parts[1] if len(parts) > 1 else ""
            user.save()

    try:
        profile, _ = Profile.objects.get_or_create(user=user)
        changed = False
        if aad_object_id and profile.teams_aad_object_id != aad_object_id:
            profile.teams_aad_object_id = aad_object_id
            changed = True
        if tenant_id and profile.teams_tenant_id != tenant_id:
            profile.teams_tenant_id = tenant_id
            changed = True
        if changed:
            profile.save(update_fields=["teams_aad_object_id", "teams_tenant_id"])
    except Exception:
        logger.exception("Failed to link Teams identity to profile for user %s", user.pk)

    return user


def teams_api_post_activity(
    service_url: str,
    conversation_id: str,
    activity_body: dict[str, Any],
    timeout: float = 30,
) -> dict | None:
    """
    POST an activity into a Bot Framework conversation. Best-effort: returns None on any
    request failure or missing token, same contract as slack_api_post. Retries once on a
    transient failure (network error, 5xx, 429) via _request_with_retry.
    """
    token = get_app_access_token()
    if not token or not service_url or not conversation_id:
        return None
    url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = _request_with_retry("POST", url, headers=headers, json=activity_body, timeout=timeout)
    if resp is None:
        return None
    try:
        resp.raise_for_status()
        return resp.json() if resp.content else {}
    except requests.RequestException as exc:
        logger.warning("Teams activity POST failed: %s", exc)
        return None


def get_teams_member_email(service_url: str, conversation_id: str, member_id: str) -> tuple[str | None, str | None]:
    """
    (email, display_name) for a Teams conversation member via the Connector REST API
    (TeamsChannelAccount) -- the inbound activity itself only reliably carries aadObjectId,
    not email, so this is a separate fetch used when first resolving an identity.
    """
    token = get_app_access_token()
    if not token or not service_url or not conversation_id or not member_id:
        return None, None
    url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/members/{member_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Teams member lookup failed: %s", exc)
        return None, None
    email = (data.get("email") or data.get("userPrincipalName") or "").strip() or None
    name = (data.get("name") or "").strip() or None
    return email, name


def teams_conversation_for_user(user) -> tuple[str, str] | None:
    """
    (service_url, conversation_id) for a 1:1 chat with this user, creating one via the
    Connector API if not already cached on Profile.
    """
    if not user:
        return None
    profile = getattr(user, "profile", None)
    aad_object_id = (getattr(profile, "teams_aad_object_id", "") or "").strip() if profile else ""
    tenant_id = (getattr(profile, "teams_tenant_id", "") or "").strip() if profile else ""
    if not aad_object_id or not tenant_id:
        return None

    cached_conv = (getattr(profile, "teams_conversation_id", "") or "").strip() if profile else ""
    inst = (
        TeamsInstallation.objects.filter(tenant_id=tenant_id, is_active=True)
        .exclude(service_url="")
        .order_by("-updated_at")
        .first()
    )
    if not inst:
        return None
    if cached_conv:
        return inst.service_url, cached_conv

    token = get_app_access_token()
    if not token:
        return None
    url = f"{inst.service_url.rstrip('/')}/v3/conversations"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "bot": {"id": settings.TEAMS_APP_ID},
        "members": [{"id": aad_object_id}],
        "channelData": {"tenant": {"id": tenant_id}},
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Teams conversation create failed for user %s: %s", user.pk, exc)
        return None

    conversation_id = (data.get("id") or "").strip()
    if not conversation_id:
        return None
    try:
        profile.teams_conversation_id = conversation_id
        profile.save(update_fields=["teams_conversation_id"])
    except Exception:
        logger.exception("Failed to cache Teams conversation id for user %s", user.pk)
    return inst.service_url, conversation_id


def install_and_conversation_for_ticket(ticket) -> tuple[TeamsInstallation | None, str | None, str | None]:
    """Resolve (installation, service_url, conversation_id) for a ticket's reporter."""
    if not ticket:
        return None, None, None
    inst = get_installation_for_ticket(ticket)
    resolved = teams_conversation_for_user(ticket.user)
    if not resolved:
        return inst, None, None
    service_url, conversation_id = resolved
    return inst, service_url, conversation_id


def install_and_conversation_for_ticket_id(ticket_id) -> tuple[TeamsInstallation | None, str | None, str | None]:
    from tickets.models import Ticket

    ticket = Ticket.objects.select_related("user", "user__profile", "team").filter(ticket_id=ticket_id).first()
    return install_and_conversation_for_ticket(ticket)
