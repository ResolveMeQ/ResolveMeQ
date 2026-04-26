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


def looks_like_slack_member_id(value: str | None) -> bool:
    s = (value or "").strip()
    return (
        len(s) >= 9
        and s[0].upper() in ("U", "W")
        and s[1:].replace("_", "").isalnum()
    )


def is_slack_shadow_user(user) -> bool:
    """True if this user was created for a Slack member (placeholder account)."""
    if not user:
        return False
    email = (getattr(user, "email", None) or "").strip().lower()
    if email.endswith("@slack.local"):
        return True
    un = (getattr(user, "username", None) or "").strip()
    return looks_like_slack_member_id(un)


def slack_shadow_display_fallback(user) -> str:
    """Human-readable label when we don't have a real name yet (avoid raw U… IDs in UI)."""
    uid = (getattr(user, "username", None) or "").strip()
    if not uid and user:
        em = (getattr(user, "email", None) or "").strip()
        if em.lower().endswith("@slack.local"):
            uid = em.split("@", 1)[0].strip()
    if looks_like_slack_member_id(uid):
        tail = uid[-4:] if len(uid) >= 4 else uid
        return f"Slack user · …{tail}"
    return "Slack user"


def display_name_for_user(user) -> str:
    """Prefer Django full name; then Slack placeholder (not raw member ID)."""
    if not user:
        return ""
    name = (user.get_full_name() if hasattr(user, "get_full_name") else "") or ""
    name = name.strip()
    if name:
        return name
    if is_slack_shadow_user(user):
        return slack_shadow_display_fallback(user)
    return (
        (getattr(user, "username", None) or "").strip()
        or (getattr(user, "email", None) or "").strip()
        or "Member"
    )


def slack_api_get(
    installation: SlackToken | None,
    method: str,
    params: dict[str, Any],
    timeout: float = 30,
) -> requests.Response | None:
    if not installation:
        return None
    url = f"https://slack.com/api/{method}"
    headers = {"Authorization": f"Bearer {installation.access_token}"}
    try:
        return requests.get(url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Slack API GET %s failed: %s", method, exc)
        return None


def _slack_real_name_from_users_info(resp: requests.Response | None) -> str | None:
    if not resp:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    if not data.get("ok"):
        logger.debug("Slack users.info not ok: %s", data.get("error"))
        return None
    u = data.get("user") or {}
    prof = u.get("profile") or {}
    for key in ("real_name", "display_name"):
        v = (prof.get(key) or "").strip()
        if v:
            return v
    legacy = (u.get("real_name") or "").strip()
    return legacy or None


def apply_slack_real_name_to_user(user: User, real_name: str) -> bool:
    """Split real_name into first/last. Returns True if user was updated."""
    real_name = (real_name or "").strip()
    if not real_name:
        return False
    parts = real_name.split(None, 1)
    user.first_name = (parts[0] or "")[:150]
    user.last_name = ((parts[1] if len(parts) > 1 else "") or "")[:150]
    user.save(update_fields=["first_name", "last_name"])
    return True


def sync_slack_shadow_profile_from_api(user: User, slack_user_id: str, installation: SlackToken | None) -> bool:
    """Fetch users.info and store real name on the shadow user. Returns True if name was set."""
    if not installation or not slack_user_id:
        return False
    resp = slack_api_get(installation, "users.info", {"user": slack_user_id})
    real_name = _slack_real_name_from_users_info(resp)
    if not real_name:
        return False
    return apply_slack_real_name_to_user(user, real_name)


def apply_slack_interaction_user_payload(user: User, slack_user: dict | None) -> bool:
    """
    Slack view/command payloads often include user.name (display / full name).
    Use when users.info is unavailable.
    """
    if not slack_user or not isinstance(slack_user, dict):
        return False
    name = (slack_user.get("name") or "").strip()
    if not name:
        return False
    return apply_slack_real_name_to_user(user, name)


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
    # Prefer explicit linked Slack identity (for users that existed before Slack integration).
    prof = getattr(user, "profile", None)
    slack_uid = (getattr(prof, "slack_user_id", "") or "").strip() if prof else ""
    if looks_like_slack_member_id(slack_uid):
        return slack_uid.upper()
    # Shadow users keep the Slack member ID in username (avoid lowercasing from email normalization).
    username = (getattr(user, "username", None) or "").strip()
    if looks_like_slack_member_id(username):
        return username.upper()

    email_raw = (user.email or "").strip()
    if email_raw.lower().endswith("@slack.local"):
        local_part = email_raw.split("@", 1)[0].strip()
        if looks_like_slack_member_id(local_part):
            return local_part.upper()
        return local_part

    return None


def get_or_create_slack_shadow_user(
    slack_user_id: str,
    *,
    installation: SlackToken | None = None,
    slack_user_payload: dict | None = None,
) -> tuple[User, bool]:
    """
    Resolve to an existing ResolveMeQ user when possible (by Slack profile email),
    otherwise create a Slack "shadow user" (email `{slack_user_id}@slack.local`).
    """
    slack_user_id = (slack_user_id or "").strip()
    if not slack_user_id:
        user = User.objects.filter(email__iexact="unknown@slack.local").first()
        if not user:
            user = User.objects.create(username="slack_user", email="unknown@slack.local", is_active=True, is_verified=False)
        return user, False

    # If we can resolve the Slack member email, prefer mapping to an existing user.
    slack_email = ""
    if installation:
        try:
            resp = slack_api_get(installation, "users.info", {"user": slack_user_id})
            if resp:
                data = resp.json() if hasattr(resp, "json") else {}
                u = (data.get("user") or {}) if isinstance(data, dict) else {}
                prof = (u.get("profile") or {}) if isinstance(u, dict) else {}
                slack_email = (prof.get("email") or "").strip().lower()
        except Exception:
            slack_email = ""

    if slack_email:
        existing = User.objects.filter(email__iexact=slack_email).first()
        if existing:
            try:
                from base.models import Profile
                p, _ = Profile.objects.get_or_create(user=existing)
                changed = False
                if looks_like_slack_member_id(slack_user_id) and (p.slack_user_id or "").strip().upper() != slack_user_id.upper():
                    p.slack_user_id = slack_user_id.upper()
                    changed = True
                if installation and (installation.team_id or "").strip() and (p.slack_team_id or "").strip() != installation.team_id:
                    p.slack_team_id = installation.team_id
                    changed = True
                if changed:
                    p.save(update_fields=["slack_user_id", "slack_team_id"])
            except Exception:
                pass
            return existing, False

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

    if not (user.first_name or user.last_name or "").strip():
        if installation:
            sync_slack_shadow_profile_from_api(user, slack_user_id, installation)
    if not (user.first_name or user.last_name or "").strip():
        apply_slack_interaction_user_payload(user, slack_user_payload)

    # Persist Slack linkage on profile too (helps DMs + avoids raw IDs elsewhere).
    try:
        from base.models import Profile
        p, _ = Profile.objects.get_or_create(user=user)
        changed = False
        if looks_like_slack_member_id(slack_user_id) and (p.slack_user_id or "").strip().upper() != slack_user_id.upper():
            p.slack_user_id = slack_user_id.upper()
            changed = True
        if installation and (installation.team_id or "").strip() and (p.slack_team_id or "").strip() != installation.team_id:
            p.slack_team_id = installation.team_id
            changed = True
        if changed:
            p.save(update_fields=["slack_user_id", "slack_team_id"])
    except Exception:
        pass

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
