"""
Slack workspace installations: token lookup per Slack team, DM channel resolution, API helper.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

from base.models import User

from integrations.connectors.base import should_retry
from integrations.models import SlackToken

logger = logging.getLogger(__name__)


def _request_with_retry(method: str, url: str, *, retry_delay: float = 1.0, **kwargs) -> requests.Response | None:
    """One retry on a transient failure (network error, 5xx, 429) -- Slack has no
    persisted circuit breaker (unlike the Okta/Google/M365 connectors), but a single
    short-backoff retry absorbs the common transient-blip case cheaply."""
    for attempt in range(2):
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            if attempt == 0:
                time.sleep(retry_delay)
                continue
            logger.warning("Slack API %s %s failed: %s", method, url, exc)
            return None
        if attempt == 0 and should_retry(resp.status_code):
            time.sleep(retry_delay)
            continue
        return resp
    return None


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
    return _request_with_retry("GET", url, headers=headers, params=params, timeout=timeout)


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
    Disabled in production unless SLACK_LEGACY_INSTALL_FALLBACK=true.
    """
    allow = getattr(settings, "SLACK_LEGACY_INSTALL_FALLBACK", None)
    if allow is None:
        allow = bool(getattr(settings, "DEBUG", False))
    if not allow:
        return None
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
    return get_installation_for_team(team)


def get_installation_for_team(team) -> SlackToken | None:
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
            logger.exception(
                "Slack users.info email lookup failed for slack_user %s (installation %s)",
                slack_user_id,
                getattr(installation, "team_id", None),
            )
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
                logger.exception(
                    "Failed to link Slack profile for existing user %s (slack_user %s)",
                    existing.pk,
                    slack_user_id,
                )
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
        logger.exception(
            "Failed to persist Slack profile linkage for user %s (slack_user %s)",
            user.pk,
            slack_user_id,
        )

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
    return _request_with_retry("POST", url, headers=headers, json=json_body, timeout=timeout)


def escalation_channel_id(installation: SlackToken | None = None) -> str:
    """Per-team channel (SlackToken.escalation_channel_id) if set, else the deployment-wide default."""
    if installation and installation.escalation_channel_id:
        return installation.escalation_channel_id.strip()
    return (getattr(settings, "SLACK_ESCALATION_CHANNEL", "") or "").strip()


def user_can_receive_slack_dm(user) -> bool:
    return bool(slack_dm_channel_for_user(user))


def _normalize_slack_channel_id(channel: str | None) -> str | None:
    ch = (channel or "").strip()
    if not ch:
        return None
    if (
        len(ch) >= 9
        and ch[0].upper() in ("U", "W")
        and ch[1:].replace("_", "").isalnum()
    ):
        return ch.upper()
    return ch


def install_and_dm_for_ticket(ticket) -> tuple[SlackToken | None, str | None]:
    """Resolve bot installation + DM channel id for a ticket's reporter."""
    if not ticket:
        return None, None
    inst = get_installation_for_ticket(ticket)
    slack_user_or_channel = _normalize_slack_channel_id(slack_dm_channel_for_user(ticket.user))
    if not inst or not slack_user_or_channel:
        return inst, slack_user_or_channel
    if slack_user_or_channel.startswith(("D", "C", "G")):
        return inst, slack_user_or_channel
    dm_resp = slack_api_post(inst, "conversations.open", {"users": slack_user_or_channel})
    if not dm_resp:
        logger.warning("Slack DM open failed for ticket %s: empty response", getattr(ticket, "ticket_id", "?"))
        return inst, slack_user_or_channel
    try:
        dm_data = dm_resp.json()
    except Exception:
        dm_data = {}
    if dm_data.get("ok") and isinstance(dm_data.get("channel"), dict):
        dm_channel_id = (dm_data["channel"].get("id") or "").strip()
        if dm_channel_id:
            return inst, dm_channel_id
    logger.warning(
        "Slack DM open failed for ticket %s user %s: %s",
        getattr(ticket, "ticket_id", "?"),
        slack_user_or_channel,
        dm_data.get("error") or getattr(dm_resp, "text", "unknown_error"),
    )
    return inst, slack_user_or_channel


def install_and_dm_for_ticket_id(ticket_id) -> tuple[SlackToken | None, str | None]:
    from tickets.models import Ticket

    ticket = Ticket.objects.select_related("user", "team").filter(ticket_id=ticket_id).first()
    return install_and_dm_for_ticket(ticket)


def persist_slack_thread_ts(ticket, message_ts: str | None) -> None:
    ts = (message_ts or "").strip()
    if not ticket or not ts:
        return
    current = (getattr(ticket, "slack_thread_ts", None) or "").strip()
    if current == ts:
        return
    ticket.slack_thread_ts = ts
    ticket.save(update_fields=["slack_thread_ts", "updated_at"])


def post_dm_for_ticket(ticket, *, text: str, blocks=None, thread_ts: str | None = None) -> bool:
    """Post a DM to the ticket reporter; persists thread root ts on the ticket when new."""
    inst, channel = install_and_dm_for_ticket(ticket)
    if not inst or not channel:
        return False
    use_thread = (thread_ts or getattr(ticket, "slack_thread_ts", None) or "").strip()
    ok, message_ts = _post_slack_dm(
        inst, channel, text=text, blocks=blocks, thread_ts=use_thread or None
    )
    if ok and not use_thread and message_ts:
        persist_slack_thread_ts(ticket, message_ts)
    return ok


def _open_dm_channel(inst, slack_user_or_channel: str) -> str | None:
    slack_user_or_channel = _normalize_slack_channel_id(slack_user_or_channel)
    if not inst or not slack_user_or_channel:
        return None
    if slack_user_or_channel.startswith(("D", "C", "G")):
        return slack_user_or_channel
    dm_resp = slack_api_post(inst, "conversations.open", {"users": slack_user_or_channel})
    if not dm_resp:
        return slack_user_or_channel
    try:
        dm_data = dm_resp.json()
    except Exception:
        dm_data = {}
    if dm_data.get("ok") and isinstance(dm_data.get("channel"), dict):
        dm_channel_id = (dm_data["channel"].get("id") or "").strip()
        if dm_channel_id:
            return dm_channel_id
    return slack_user_or_channel


def _post_slack_dm(
    inst: SlackToken | None,
    channel: str,
    *,
    text: str,
    blocks=None,
    thread_ts: str | None = None,
) -> tuple[bool, str | None]:
    if not inst or not channel:
        return False, None
    payload: dict[str, Any] = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    use_thread = (thread_ts or "").strip()
    if use_thread:
        payload["thread_ts"] = use_thread
    resp = slack_api_post(inst, "chat.postMessage", payload)
    try:
        data = resp.json() if resp else {}
    except Exception:
        data = {}
    if data.get("ok"):
        return True, data.get("ts")
    logger.warning(
        "Slack DM failed for channel %s: %s",
        channel,
        data.get("error") or getattr(resp, "text", resp),
    )
    return False, None


def post_dm_for_user_on_team(user, team, *, text: str, blocks=None) -> bool:
    """Post a DM to a ResolveMeQ user when their workspace has Slack connected."""
    if not user_can_receive_slack_dm(user):
        return False
    inst = get_installation_for_team(team)
    slack_user = slack_dm_channel_for_user(user)
    channel = _open_dm_channel(inst, slack_user) if slack_user else None
    if not channel:
        return False
    ok, _ = _post_slack_dm(inst, channel, text=text, blocks=blocks)
    return ok


def notify_workflow_step_active(workflow, step) -> None:
    """DM each team member who can receive Slack when a workflow step becomes active."""
    team = getattr(workflow, "team", None)
    if not team:
        return
    from workflows.notifications import _team_recipients

    template_name = workflow.template.name if workflow.template_id else "Workflow"
    if workflow.ticket_id:
        context = f"Linked to ticket #{workflow.ticket_id}."
    else:
        context = "Open Workflows in ResolveMeQ to claim it."
    due_line = ""
    if getattr(step, "due_at", None):
        due_line = f"\nDue by {step.due_at.strftime('%b %d, %Y %H:%M UTC')}."
    text = (
        f"*New workflow step ready*\n"
        f"\"{step.title}\" in *{template_name}* needs attention.\n"
        f"{context}{due_line}"
    )
    for user in _team_recipients(team):
        post_dm_for_user_on_team(user, team, text=text)


def notify_ticket_reporter_message(ticket, *, title: str, body: str, actor_name: str = "") -> bool:
    """Sync a support reply or comment from the web app to the reporter's Slack DM."""
    if not user_can_receive_slack_dm(ticket.user):
        return False
    actor = (actor_name or "Support").strip()
    text = f"*{title}*\n{actor}: {body}"
    return post_dm_for_ticket(ticket, text=text)
