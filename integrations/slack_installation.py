"""
Slack workspace installations: token lookup per Slack team, DM channel resolution, API helper.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

from base.models import User

from integrations.models import SlackToken

logger = logging.getLogger(__name__)


def legacy_installation_fallback() -> SlackToken | None:
    """
    When only one bot installation exists (typical single-tenant dev), use it if workspace-specific
    lookup fails. Avoids using arbitrary rows when multiple workspaces are connected.
    """
    qs = SlackToken.objects.filter(is_active=True)
    if qs.count() == 1:
        return qs.select_related("resolvemeq_team", "installed_by").first()
    orphan = qs.filter(resolvemeq_team__isnull=True)
    if orphan.count() == 1:
        return orphan.select_related("resolvemeq_team", "installed_by").first()
    return None


def get_installation_for_slack_team(slack_team_id: str | None) -> SlackToken | None:
    if slack_team_id:
        inst = (
            SlackToken.objects.filter(team_id=slack_team_id, is_active=True)
            .select_related("resolvemeq_team", "installed_by")
            .order_by("-updated_at")
            .first()
        )
        if inst:
            return inst
        logger.warning("Slack installation missing for workspace %s; trying legacy fallback", slack_team_id)
    return legacy_installation_fallback()


def get_installation_for_ticket(ticket) -> SlackToken | None:
    team = getattr(ticket, "team", None)
    if team is None:
        return legacy_installation_fallback()
    inst = (
        SlackToken.objects.filter(resolvemeq_team=team, is_active=True)
        .select_related("resolvemeq_team", "installed_by")
        .order_by("-updated_at")
        .first()
    )
    if inst:
        return inst
    return legacy_installation_fallback()


def slack_dm_channel_for_user(user: User | None) -> str | None:
    """Slack user id to pass as `channel` for chat.postMessage DM, or None if not Slack-backed."""
    if not user:
        return None
    # Shadow users usually keep the Slack member ID in username. Prefer it to avoid
    # accidental lowercasing from email normalization.
    un = (getattr(user, "username", None) or "").strip()
    if len(un) >= 9 and un[0].upper() in ("U", "W") and un[1:].replace("_", "").isalnum():
        return un.upper()

    # Fallback for legacy rows that only have slack-local email.
    email_raw = (user.email or "").strip()
    if email_raw.lower().endswith("@slack.local"):
        local_part = email_raw.split("@", 1)[0].strip()
        if len(local_part) >= 9 and local_part[0].upper() in ("U", "W") and local_part[1:].replace("_", "").isalnum():
            return local_part.upper()
        return local_part

    return None


def get_or_create_slack_shadow_user(slack_user_id: str) -> tuple[User, bool]:
    """Placeholder ResolveMeQ user for a Slack member (email `{slack_user_id}@slack.local`)."""
    email = f"{slack_user_id}@slack.local"
    user, created = User.objects.get_or_create(
        username=slack_user_id,
        defaults={
            "email": email,
            "is_active": True,
            "is_verified": False,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif not (user.email or "").strip():
        user.email = email
        user.save(update_fields=["email"])
    return user, created


def slack_api_post(
    installation: SlackToken | None,
    method: str,
    json_body: dict[str, Any],
    timeout: float = 30,
) -> requests.Response | None:
    """POST to https://slack.com/api/{method} (e.g. chat.postMessage, views.open)."""
    if not installation:
        return None
    url = f"https://slack.com/api/{method}"
    headers = {
        "Authorization": f"Bearer {installation.access_token}",
        "Content-Type": "application/json",
    }
    try:
        return requests.post(url, headers=headers, json=json_body, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Slack API %s failed: %s", method, exc)
        return None


def escalation_channel_id() -> str:
    return (getattr(settings, "SLACK_ESCALATION_CHANNEL", "") or "").strip()
