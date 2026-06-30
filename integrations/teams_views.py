"""
Microsoft Teams bot views: OAuth-equivalent linking flow, outbound notifications
(Adaptive Cards), and the inbound messaging endpoint.

Mirrors integrations/views.py's Slack functions one-for-one where a direct analog exists --
see the Teams integration plan for the full reasoning on where Teams genuinely differs
(no redirect-based install, JWT auth instead of HMAC, one inbound endpoint instead of four).
"""
from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from integrations import teams_bot
from integrations.models import TeamsInstallation, TeamsLinkCode

logger = logging.getLogger(__name__)

LINK_CODE_TTL_MINUTES = 15


# ---------------------------------------------------------------------------
# Linking flow (Teams' equivalent of Slack's OAuth start/redirect/status/disconnect)
# ---------------------------------------------------------------------------

def _team_membership_or_403(request, team_id):
    if not team_id:
        return None, Response({"detail": "team_id is required."}, status=400)
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return None, Response({"detail": "Team not found."}, status=404)
    if team.owner_id != request.user.pk and not team.members.filter(pk=request.user.pk).exists():
        return None, Response({"detail": "You are not a member of this team."}, status=403)
    return team, None


def _resolve_team_id(request):
    team_id = request.GET.get("team_id") or request.data.get("team_id") if hasattr(request, "data") else request.GET.get("team_id")
    if not team_id:
        prefs = getattr(request.user, "preferences", None)
        if prefs and prefs.active_team_id:
            team_id = str(prefs.active_team_id)
    return team_id


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teams_link_start(request):
    """
    Generate a short-lived linking code for the current user's team. The user adds the bot
    to a Teams team/channel and sends it `link <code>` to attach that installation here.
    No redirect URL to return, unlike Slack's OAuth start -- this is a code, not a link.
    """
    team_id = _resolve_team_id(request)
    team, err = _team_membership_or_403(request, team_id)
    if err:
        return err

    code = None
    for _ in range(3):
        candidate = secrets.token_hex(4).upper()
        if not TeamsLinkCode.objects.filter(code=candidate).exists():
            code = candidate
            break
    if not code:
        return Response({"detail": "Could not generate a linking code, try again."}, status=503)

    expires_at = timezone.now() + timezone.timedelta(minutes=LINK_CODE_TTL_MINUTES)
    TeamsLinkCode.objects.create(
        code=code, resolvemeq_team=team, created_by=request.user, expires_at=expires_at
    )
    return Response({
        "code": code,
        "expires_at": expires_at.isoformat(),
        "instructions": (
            "1. Add the ResolveMeQ bot to your Teams team or a channel. "
            f"2. Message the bot: link {code}. "
            "3. This code expires in 15 minutes."
        ),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teams_integration_status(request):
    """Whether the current (or requested) team has an active Teams installation."""
    team_id = _resolve_team_id(request)
    if not team_id:
        return Response({"connected": False, "tenant_id": None, "updated_at": None})
    team, err = _team_membership_or_403(request, team_id)
    if err:
        return err
    inst = (
        TeamsInstallation.objects.filter(resolvemeq_team=team, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return Response({
        "connected": bool(inst),
        "tenant_id": inst.tenant_id if inst else None,
        "updated_at": inst.updated_at.isoformat() if inst and inst.updated_at else None,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def teams_disconnect(request):
    """Deactivate the Teams installation link for the requested ResolveMeQ team."""
    team_id = request.data.get("team_id") or request.GET.get("team_id")
    team, err = _team_membership_or_403(request, team_id)
    if err:
        return err
    updated = TeamsInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    return Response({"disconnected": bool(updated), "team_id": str(team.id)})


# ---------------------------------------------------------------------------
# Adaptive Card helpers
# ---------------------------------------------------------------------------

def _card_activity(body: list, actions: list | None = None, summary: str = "") -> dict:
    card: dict[str, Any] = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return {
        "type": "message",
        "summary": summary,
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    }


def _text_activity(text: str) -> dict:
    return {"type": "message", "text": text}


def _tb(text: str, *, weight: str | None = None, wrap: bool = True, size: str | None = None) -> dict:
    block: dict[str, Any] = {"type": "TextBlock", "text": text, "wrap": wrap}
    if weight:
        block["weight"] = weight
    if size:
        block["size"] = size
    return block


def _submit_action(title: str, action: str, ticket_id, *, style: str | None = None) -> dict:
    out = {"type": "Action.Submit", "title": title, "data": {"action": action, "ticket_id": str(ticket_id)}}
    if style:
        out["style"] = style
    return out


def _clean_list(v, limit=8):
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        text = str(item).strip() if item is not None else ""
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _send(ticket_id, activity: dict) -> bool:
    inst, service_url, conversation_id = teams_bot.install_and_conversation_for_ticket_id(ticket_id)
    if not inst or not service_url or not conversation_id:
        logger.info("Teams notify skipped (ticket_id=%s): no installation or conversation for reporter", ticket_id)
        return False
    result = teams_bot.teams_api_post_activity(service_url, conversation_id, activity)
    if result is None:
        logger.warning("Teams notify failed (ticket_id=%s)", ticket_id)
        return False
    return True


# ---------------------------------------------------------------------------
# Outbound notifications -- one per Slack counterpart (integrations/views.py)
# ---------------------------------------------------------------------------

def notify_user_agent_response(ticket_id, agent_response, **_kwargs):
    """Teams DM equivalent of notify_user_agent_response (thread_ts has no Teams analog used here)."""
    import json as _json

    if isinstance(agent_response, str):
        try:
            agent_response = _json.loads(agent_response)
        except Exception:
            agent_response = {}
    if not isinstance(agent_response, dict):
        agent_response = {}

    analysis = agent_response.get("analysis") or {}
    solution = agent_response.get("solution") or {}
    recommendations = agent_response.get("recommendations") or {}
    reasoning = (agent_response.get("reasoning") or "").strip()
    confidence = agent_response.get("confidence")

    header = f"🤖 AI update for ticket #{ticket_id}"
    if confidence is not None:
        try:
            header += f" (confidence {float(confidence):.0%})"
        except (TypeError, ValueError):
            pass
    body = [_tb(header, weight="Bolder", size="Medium")]

    overview = []
    for label, key in [("Category", "category"), ("Severity", "severity"), ("Priority", "priority")]:
        value = (analysis.get(key) or "").strip() if isinstance(analysis.get(key), str) else analysis.get(key)
        if value:
            overview.append(f"**{label}:** {value}")
    if overview:
        body.append(_tb("  ·  ".join(overview)))

    if reasoning:
        body.append(_tb(f"**What I found**\n{reasoning[:1200]}"))

    steps = _clean_list(solution.get("steps"), limit=7) or _clean_list(recommendations.get("resolution_steps"), limit=7)
    if steps:
        body.append(_tb("**Recommended steps**\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))))

    actions = [
        _submit_action("✅ Mark as Resolved", "resolve_ticket", ticket_id, style="positive"),
        _submit_action("✏️ Clarify", "clarify_ticket", ticket_id),
        _submit_action("🚨 Escalate", "escalate_ticket", ticket_id, style="destructive"),
        _submit_action("💬 Feedback", "feedback_text", ticket_id),
    ]
    _send(ticket_id, _card_activity(body, actions, summary=f"Agent response for ticket #{ticket_id}"))


def notify_user_auto_resolution(ticket_id, params, **_kwargs):
    body = [_tb(f"✅ Ticket #{ticket_id} Auto-Resolved", weight="Bolder"),
            _tb("Your issue has been automatically resolved by our AI agent!")]
    steps = params.get("resolution_steps") or []
    if isinstance(steps, list) and steps:
        body.append(_tb("**Resolution steps**\n" + "\n".join(f"• {s}" for s in steps)))
    reasoning = (params.get("reasoning") or "").strip()
    if reasoning:
        body.append(_tb(f"**Why this solution:** {reasoning}"))
    actions = [
        _submit_action("✅ Issue Resolved", "confirm_resolution", ticket_id, style="positive"),
        _submit_action("❌ Still Having Issues", "reopen_ticket", ticket_id, style="destructive"),
    ]
    _send(ticket_id, _card_activity(body, actions, summary=f"Ticket #{ticket_id} auto-resolved"))


def notify_ticket_claimed(ticket_id, agent_name, eta_text="", **_kwargs):
    text = f"✅ {agent_name} is now looking into ticket #{ticket_id}."
    if eta_text:
        text += f" Typically resolved {eta_text}."
    _send(ticket_id, _text_activity(text))


def notify_escalation(ticket_id, params, **_kwargs):
    body = [
        _tb(f"🚨 Ticket #{ticket_id} Escalated", weight="Bolder"),
        _tb(f"Your issue has been escalated to our {params.get('suggested_team', 'support team')} for specialized assistance."),
        _tb(f"**Reason:** {params.get('escalation_reason', 'Complex issue requiring human expertise')}\n"
            f"**Priority:** {str(params.get('priority', 'medium')).upper()}"),
        _tb(f"A human support agent will review your case and contact you {params.get('eta_text', 'shortly')}."),
    ]
    _send(ticket_id, _card_activity(body, summary=f"Ticket #{ticket_id} escalated"))


def notify_support_escalation_teams(ticket, params):
    """Posts to the team's escalation-channel conversation (Teams analog of SLACK_ESCALATION_CHANNEL)."""
    resolved = teams_bot.escalation_conversation_for_team(getattr(ticket, "team", None))
    if not resolved:
        return
    service_url, conversation_id = resolved
    user_name = teams_bot.display_name_for_teams_user(ticket.user)
    desc = (ticket.description or "")[:300]
    if len(ticket.description or "") > 300:
        desc += "..."
    body = [
        _tb(f"🚨 New Escalation – Ticket #{ticket.ticket_id}", weight="Bolder"),
        _tb(f"**From:** {user_name}\n**Subject:** {ticket.issue_type or 'No title'}"),
        _tb(f"**Description:**\n{desc or 'No description'}"),
    ]
    summary = (params or {}).get("conversation_summary", "")
    if summary:
        body.append(_tb(f"**Conversation context:**\n{summary[:400]}"))
    handoff = ((params or {}).get("handoff_summary") or (params or {}).get("handoff_text") or "").strip()
    if handoff:
        body.append(_tb(f"**Handoff:**\n{handoff[:500]}"))
    web = getattr(settings, "FRONTEND_URL", "https://app.resolvemeq.net").rstrip("/")
    actions = [{"type": "Action.OpenUrl", "title": "View Ticket", "url": f"{web}/tickets?highlight={ticket.ticket_id}"}]
    activity = _card_activity(body, actions, summary=f"Ticket #{ticket.ticket_id} escalated")
    result = teams_bot.teams_api_post_activity(service_url, conversation_id, activity)
    if result is None:
        logger.warning("Teams escalation-channel post failed for ticket %s", ticket.ticket_id)


def request_clarification_from_user(ticket_id, params, **_kwargs):
    questions = params.get("questions") or []
    questions_text = "\n".join(f"• {q}" for q in questions)
    body = [
        _tb(f"❓ Need More Information – Ticket #{ticket_id}", weight="Bolder"),
        _tb("To provide you with the best solution, I need some additional details:"),
        _tb(questions_text),
    ]
    actions = [_submit_action("💬 Provide Details", "clarify_ticket", ticket_id, style="positive")]
    _send(ticket_id, _card_activity(body, actions, summary=f"Clarification needed for ticket #{ticket_id}"))


def notify_resolution_followup(ticket_id, **_kwargs):
    _send(ticket_id, _text_activity(
        f"👋 Checking in on ticket #{ticket_id} — did the fix work? Reply here and let us know."
    ))


def notify_user_ticket_resolved(ticket):
    from tickets.models import Ticket

    if not isinstance(ticket, Ticket):
        ticket = Ticket.objects.select_related("user", "team").filter(ticket_id=ticket).first()
    if not ticket:
        return
    _send(ticket.ticket_id, _text_activity(f"🛠️ Your ticket #{ticket.ticket_id} is now marked as resolved."))


def notify_ticket_reporter_message(ticket, *, title: str, body: str, actor_name: str = ""):
    """Teams analog of slack_installation.notify_ticket_reporter_message -- used by chat replies/comments."""
    prefix = f"{actor_name}: " if actor_name else ""
    _send(ticket.ticket_id, _text_activity(f"{title}\n\n{prefix}{body}"))


# ---------------------------------------------------------------------------
# Inbound JWT auth (Teams' equivalent of Slack's HMAC signature check)
# ---------------------------------------------------------------------------

def verify_teams_request(activity_dict: dict, auth_header: str) -> bool:
    """
    Validates the inbound request's JWT against Microsoft's published keys, using the
    Bot Framework SDK rather than hand-rolling JWKS validation (see the Teams integration
    plan for why). Any failure -- missing app credentials, malformed token, wrong audience,
    expired token -- is treated as unauthenticated, same contract as verify_slack_request.
    """
    import asyncio

    app_id = getattr(settings, "TEAMS_APP_ID", "") or ""
    app_password = getattr(settings, "TEAMS_APP_PASSWORD", "") or ""
    if not app_id or not app_password:
        return False
    if not auth_header:
        return False
    try:
        from botbuilder.schema import Activity
        from botframework.connector.auth import JwtTokenValidation, SimpleCredentialProvider

        activity = Activity().deserialize(activity_dict)
        credentials = SimpleCredentialProvider(app_id, app_password)
        asyncio.run(JwtTokenValidation.authenticate_request(activity, auth_header, credentials))
        return True
    except Exception as exc:
        logger.warning("Teams request auth failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Inbound messaging endpoint -- one endpoint for messages, install events, and
# card-button submissions, routed by activity type (see plan for why Teams uses
# one endpoint where Slack uses four).
# ---------------------------------------------------------------------------

def _send_raw(service_url: str, conversation_id: str, activity: dict) -> None:
    if not service_url or not conversation_id:
        return
    teams_bot.teams_api_post_activity(service_url, conversation_id, activity)


@csrf_exempt
def teams_messages(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        return HttpResponse(status=400)
    if not isinstance(body, dict):
        return HttpResponse(status=400)
    auth_header = request.headers.get("Authorization", "")
    if not verify_teams_request(body, auth_header):
        return HttpResponse(status=401)

    activity_type = body.get("type")
    if activity_type == "message":
        if body.get("value"):
            return _handle_card_submit(body)
        return _handle_text_message(body)
    if activity_type == "conversationUpdate":
        return _handle_conversation_update(body)
    # invoke (Action.Execute / Universal Action Model) and anything else: ack only, we don't use it.
    return HttpResponse(status=200)


# ---------------------------------------------------------------------------
# conversationUpdate -- bot added/removed from a Teams team
# ---------------------------------------------------------------------------

def _handle_conversation_update(activity: dict):
    channel_data = activity.get("channelData") or {}
    teams_team_id = (channel_data.get("team") or {}).get("id", "")
    tenant_id = (channel_data.get("tenant") or {}).get("id", "")
    service_url = activity.get("serviceUrl", "")
    conversation_id = (activity.get("conversation") or {}).get("id", "")
    recipient_id = (activity.get("recipient") or {}).get("id", "")

    if not teams_team_id:
        # Personal/1:1 conversationUpdate -- nothing to upsert until the bot is in a team.
        return HttpResponse(status=200)

    members_removed = activity.get("membersRemoved") or []
    if any(m.get("id") == recipient_id for m in members_removed):
        TeamsInstallation.objects.filter(tenant_id=tenant_id, teams_team_id=teams_team_id).update(is_active=False)
        return HttpResponse(status=200)

    members_added = activity.get("membersAdded") or []
    if members_added or service_url:
        TeamsInstallation.objects.update_or_create(
            tenant_id=tenant_id,
            teams_team_id=teams_team_id,
            defaults={"conversation_id": conversation_id, "service_url": service_url, "is_active": True},
        )
    return HttpResponse(status=200)


# ---------------------------------------------------------------------------
# Plain-text messages -- link code, status command, ticket-creation trigger
# ---------------------------------------------------------------------------

def _activity_routing(activity: dict) -> dict:
    channel_data = activity.get("channelData") or {}
    conversation = activity.get("conversation") or {}
    from_user = activity.get("from") or {}
    return {
        "teams_team_id": (channel_data.get("team") or {}).get("id", ""),
        "tenant_id": (channel_data.get("tenant") or {}).get("id", ""),
        "service_url": activity.get("serviceUrl", ""),
        "conversation_id": conversation.get("id", ""),
        "aad_object_id": from_user.get("aadObjectId") or from_user.get("id", ""),
        "from_name": from_user.get("name", ""),
    }


def _resolve_user_for_activity(route: dict) -> "User | None":
    """Resolve (and link) the ResolveMeQ user behind an inbound activity, fetching email
    via the Connector member-lookup API on first contact (the activity payload itself
    doesn't reliably carry email)."""
    if not route["aad_object_id"]:
        return None
    email, name = teams_bot.get_teams_member_email(
        route["service_url"], route["conversation_id"], route["aad_object_id"]
    )
    return teams_bot.get_or_link_teams_user(
        route["aad_object_id"],
        route["tenant_id"],
        email=email,
        display_name=name or route["from_name"],
    )


def _team_for_route(route: dict):
    """Resolve which ResolveMeQ team a command applies to. Channel messages carry a
    teams_team_id directly; personal/DM messages don't, so fall back to the most
    recently updated linked installation for the tenant (see plan edge case 4)."""
    qs = TeamsInstallation.objects.filter(tenant_id=route["tenant_id"], is_active=True).exclude(resolvemeq_team=None)
    if route["teams_team_id"]:
        qs = qs.filter(teams_team_id=route["teams_team_id"])
    inst = qs.order_by("-updated_at").first()
    return inst.resolvemeq_team if inst else None


def _consume_link_code(activity: dict, route: dict, code: str):
    if not route["teams_team_id"]:
        _send_raw(route["service_url"], route["conversation_id"], _text_activity(
            "Send \"link <code>\" in the Teams team/channel you added the bot to, not a direct message."
        ))
        return HttpResponse(status=200)

    link = (
        TeamsLinkCode.objects.filter(code=code, consumed_at__isnull=True)
        .select_related("resolvemeq_team", "created_by")
        .first()
    )
    if not link or link.expires_at < timezone.now():
        _send_raw(route["service_url"], route["conversation_id"], _text_activity(
            "That linking code is invalid or expired. Generate a new one from Settings."
        ))
        return HttpResponse(status=200)

    inst, _created = TeamsInstallation.objects.update_or_create(
        tenant_id=route["tenant_id"],
        teams_team_id=route["teams_team_id"],
        defaults={
            "conversation_id": route["conversation_id"],
            "service_url": route["service_url"],
            "resolvemeq_team": link.resolvemeq_team,
            "installed_by": link.created_by,
            "is_active": True,
        },
    )
    link.consumed_at = timezone.now()
    link.consumed_by_installation = inst
    link.save(update_fields=["consumed_at", "consumed_by_installation"])
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(
        f"✅ Connected! This Teams team is now linked to ResolveMeQ team \"{link.resolvemeq_team.name}\"."
    ))
    return HttpResponse(status=200)


def _handle_status_command(route: dict):
    from tickets.models import Ticket

    user = _resolve_user_for_activity(route)
    if not user:
        _send_raw(route["service_url"], route["conversation_id"], _text_activity(
            "Couldn't identify your account. Try again from within Teams."
        ))
        return HttpResponse(status=200)
    team = _team_for_route(route)
    qs = Ticket.objects.filter(user=user)
    if team:
        qs = qs.filter(team=team)
    tickets = list(qs.order_by("-created_at")[:15])
    if tickets:
        lines = [f"• Ticket #{t.ticket_id}: {t.issue_type} — {t.status.capitalize()}" for t in tickets]
        text = "**Your Tickets:**\n" + "\n".join(lines)
    else:
        text = "You have no tickets."
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(text))
    return HttpResponse(status=200)


def _send_ticket_creation_card(route: dict):
    from tickets.models import Ticket

    category_choices = [{"title": label, "value": value} for value, label in Ticket.CATEGORY_CHOICES]
    body = [
        _tb("New IT Request", weight="Bolder", size="Medium"),
        {
            "type": "Input.ChoiceSet",
            "id": "category",
            "label": "Category",
            "style": "compact",
            "choices": category_choices,
            "isRequired": True,
            "errorMessage": "Select a category.",
        },
        {
            "type": "Input.Text",
            "id": "subject",
            "label": "Subject",
            "placeholder": "Brief summary of the issue",
            "maxLength": 100,
            "isRequired": True,
            "errorMessage": "Enter a short subject.",
        },
        {
            "type": "Input.ChoiceSet",
            "id": "urgency",
            "label": "Urgency",
            "style": "compact",
            "choices": [
                {"title": "Low", "value": "low"},
                {"title": "Medium", "value": "medium"},
                {"title": "High", "value": "high"},
            ],
            "value": "medium",
        },
        {
            "type": "Input.Text",
            "id": "description",
            "label": "Description (optional)",
            "isMultiline": True,
        },
    ]
    actions = [{"type": "Action.Submit", "title": "Submit", "data": {"action": "create_ticket"}}]
    _send_raw(route["service_url"], route["conversation_id"], _card_activity(body, actions, summary="New IT Request"))
    return HttpResponse(status=200)


def _handle_text_message(activity: dict):
    text = (activity.get("text") or "").strip()
    route = _activity_routing(activity)
    lowered = text.lower()

    if lowered.startswith("link "):
        code = text[5:].strip().upper()
        return _consume_link_code(activity, route, code)
    if lowered == "status":
        return _handle_status_command(route)
    if lowered in ("new", "new ticket", "create ticket", "ticket"):
        return _send_ticket_creation_card(route)
    # Acknowledge without auto-replying to arbitrary text, mirrors Slack's events handler.
    logger.debug("Teams message ignored (conversation=%s)", route["conversation_id"])
    return HttpResponse(status=200)


# ---------------------------------------------------------------------------
# Adaptive Card Action.Submit dispatch -- Teams delivers these as `message`
# activities with `value` populated (not `invoke`), unlike Slack's separate
# interactivity endpoint.
# ---------------------------------------------------------------------------

def _handle_card_submit(activity: dict):
    value = activity.get("value") or {}
    action = (value.get("action") or "").strip()
    route = _activity_routing(activity)

    if action == "create_ticket":
        return _submit_ticket_creation(route, value)
    if action == "resolve_ticket":
        return _action_resolve_ticket(route, value)
    if action == "clarify_ticket":
        return _action_send_clarify_card(route, value)
    if action == "clarify_submit":
        return _action_clarify_submit(route, value)
    if action == "escalate_ticket":
        return _action_escalate_ticket(route, value)
    if action == "feedback_text":
        return _action_send_feedback_card(route, value)
    if action == "feedback_submit":
        return _action_feedback_submit(route, value)
    if action in ("feedback_positive", "feedback_negative"):
        return _action_feedback_quick(route, value, action)
    if action == "confirm_resolution":
        return _action_confirm_resolution(route, value)
    if action == "reopen_ticket":
        return _action_reopen_ticket(route, value)
    return HttpResponse(status=200)


def _submit_ticket_creation(route: dict, value: dict):
    subject = (value.get("subject") or "").strip()
    if not subject:
        _send_raw(route["service_url"], route["conversation_id"], _text_activity("Subject is required. Send \"new\" to try again."))
        return HttpResponse(status=200)
    user = _resolve_user_for_activity(route)
    if not user:
        _send_raw(route["service_url"], route["conversation_id"], _text_activity("Couldn't identify your account."))
        return HttpResponse(status=200)
    team = _team_for_route(route)
    from tickets.services import compose_issue_type, create_ticket_with_reporter

    ticket = create_ticket_with_reporter(
        user,
        team,
        issue_type=compose_issue_type(subject, value.get("urgency")),
        description=value.get("description") or "",
        category=value.get("category") or "other",
        status="new",
    )
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(
        f"🎟️ Ticket #{ticket.ticket_id} created successfully! We'll get back to you soon."
    ))
    return HttpResponse(status=200)


def _action_resolve_ticket(route: dict, value: dict):
    from tickets.models import Ticket

    ticket_id = value.get("ticket_id")
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
    except Ticket.DoesNotExist:
        _send_raw(route["service_url"], route["conversation_id"], _text_activity(f"❌ Ticket #{ticket_id} not found."))
        return HttpResponse(status=200)
    ticket.status = "resolved"
    ticket.save(update_fields=["status", "updated_at"])
    actions = [
        _submit_action("👍 Helpful", "feedback_positive", ticket_id, style="positive"),
        _submit_action("👎 Not Helpful", "feedback_negative", ticket_id),
    ]
    body = [_tb(f"✅ Ticket #{ticket_id} marked as resolved."), _tb("How helpful was the agent's response?")]
    _send_raw(route["service_url"], route["conversation_id"], _card_activity(body, actions))
    return HttpResponse(status=200)


def _action_send_clarify_card(route: dict, value: dict):
    ticket_id = value.get("ticket_id")
    body = [
        _tb("Provide More Info", weight="Bolder"),
        {"type": "Input.Text", "id": "description", "label": "Description (required)", "isMultiline": True, "isRequired": True},
        {"type": "Input.Text", "id": "issue_type", "label": "Issue Type (required)", "isRequired": True},
    ]
    actions = [{"type": "Action.Submit", "title": "Submit", "data": {"action": "clarify_submit", "ticket_id": str(ticket_id)}}]
    _send_raw(route["service_url"], route["conversation_id"], _card_activity(body, actions))
    return HttpResponse(status=200)


def _action_clarify_submit(route: dict, value: dict):
    from tickets.models import Ticket, TicketInteraction

    ticket_id = value.get("ticket_id")
    description = (value.get("description") or "").strip()
    issue_type = (value.get("issue_type") or "").strip()
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
    except Ticket.DoesNotExist:
        _send_raw(route["service_url"], route["conversation_id"], _text_activity(f"❌ Ticket #{ticket_id} not found."))
        return HttpResponse(status=200)
    ticket.description = description
    ticket.issue_type = issue_type
    if (ticket.status or "").lower() == "pending_clarification":
        ticket.status = "open"
    ticket.save()
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="clarification",
        content=f"User clarified: Description='{description}', Issue Type='{issue_type}'",
    )
    from tickets.tasks import process_ticket_with_agent

    process_ticket_with_agent.delay(ticket.ticket_id)
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(f"🔄 Thanks — Ticket #{ticket_id} is being reprocessed."))
    return HttpResponse(status=200)


def _action_escalate_ticket(route: dict, value: dict):
    from tickets.models import Ticket
    from tickets.tasks import handle_escalate

    ticket_id = value.get("ticket_id")
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        if (ticket.status or "").lower() == "escalated":
            msg = f"Ticket #{ticket_id} is already escalated."
        else:
            handle_escalate(ticket, {
                "escalation_reason": "User requested escalation via Teams.",
                "reason": "Requested human help",
            })
            msg = f"🚨 Ticket #{ticket_id} has been escalated. An IT admin will review it shortly."
    except Ticket.DoesNotExist:
        msg = f"❌ Ticket #{ticket_id} not found."
    except Exception as exc:
        logger.exception("Teams escalate failed for ticket %s", ticket_id)
        msg = f"Could not escalate Ticket #{ticket_id}: {exc}"
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(msg))
    return HttpResponse(status=200)


def _action_send_feedback_card(route: dict, value: dict):
    ticket_id = value.get("ticket_id")
    body = [
        _tb("Provide Feedback", weight="Bolder"),
        {"type": "Input.Text", "id": "feedback_text", "label": "Your Feedback (required)", "isMultiline": True, "isRequired": True},
    ]
    actions = [{"type": "Action.Submit", "title": "Send", "data": {"action": "feedback_submit", "ticket_id": str(ticket_id)}}]
    _send_raw(route["service_url"], route["conversation_id"], _card_activity(body, actions))
    return HttpResponse(status=200)


def _action_feedback_submit(route: dict, value: dict):
    from tickets.models import Ticket, TicketInteraction

    ticket_id = value.get("ticket_id")
    feedback = (value.get("feedback_text") or "").strip()
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        TicketInteraction.objects.create(
            ticket=ticket, user=ticket.user, interaction_type="feedback", content=f"User feedback: {feedback}",
        )
    except Ticket.DoesNotExist:
        pass
    _send_raw(route["service_url"], route["conversation_id"], _text_activity("Thank you for your feedback! Our IT team will review it shortly."))
    return HttpResponse(status=200)


def _action_feedback_quick(route: dict, value: dict, action: str):
    from tickets.models import Ticket, TicketInteraction

    ticket_id = value.get("ticket_id")
    feedback = "helpful" if action == "feedback_positive" else "not helpful"
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        TicketInteraction.objects.create(
            ticket=ticket, user=ticket.user, interaction_type="feedback", content=f"User marked agent response as: {feedback}",
        )
        ticket.sync_to_knowledge_base()
    except Exception:
        pass
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(f"Thank you for your feedback on Ticket #{ticket_id}: *{feedback}*."))
    return HttpResponse(status=200)


def _action_confirm_resolution(route: dict, value: dict):
    from tickets.models import Ticket, TicketInteraction

    ticket_id = value.get("ticket_id")
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        if (ticket.status or "").lower() != "resolved":
            ticket.status = "resolved"
            ticket.save(update_fields=["status", "updated_at"])
            ticket.sync_to_knowledge_base()
        TicketInteraction.objects.create(
            ticket=ticket, user=ticket.user, interaction_type="feedback", content="User confirmed auto-resolution via Teams.",
        )
        msg = f"✅ Thanks for confirming Ticket #{ticket_id} is resolved."
    except Ticket.DoesNotExist:
        msg = f"❌ Ticket #{ticket_id} not found."
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(msg))
    return HttpResponse(status=200)


def _action_reopen_ticket(route: dict, value: dict):
    from tickets.models import Ticket, TicketInteraction
    from tickets.tasks import handle_escalate

    ticket_id = value.get("ticket_id")
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        ticket.status = "open"
        ticket.save(update_fields=["status", "updated_at"])
        TicketInteraction.objects.create(
            ticket=ticket, user=ticket.user, interaction_type="user_message", content="User reported the issue is still occurring via Teams.",
        )
        handle_escalate(ticket, {
            "escalation_reason": "User reported issue persists after auto-resolution.",
            "reason": "Requested human help",
            "priority": "high",
        })
        msg = f"🚨 Ticket #{ticket_id} reopened and escalated for human review."
    except Ticket.DoesNotExist:
        msg = f"❌ Ticket #{ticket_id} not found."
    _send_raw(route["service_url"], route["conversation_id"], _text_activity(msg))
    return HttpResponse(status=200)
