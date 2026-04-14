"""
Slack integration views for OAuth, events, slash commands, and interactive actions.
Handles Slack authentication, event verification, ticket creation, notifications, and more.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.parse

import requests
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team, User

from integrations import slack_installation as slack_inst
from integrations.models import SlackToken

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def slack_oauth_start(request):
    """
    Start Slack OAuth for the current user's ResolveMeQ team.
    Query: team_id (UUID, optional if user has an active_team on preferences).
    """
    team_id = request.GET.get("team_id")
    if not team_id:
        prefs = getattr(request.user, "preferences", None)
        if prefs and prefs.active_team_id:
            team_id = str(prefs.active_team_id)
    if not team_id:
        return Response({"detail": "team_id query parameter or active_team required."}, status=400)
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return Response({"detail": "Team not found."}, status=404)
    if team.owner_id != request.user.pk and not team.members.filter(pk=request.user.pk).exists():
        return Response({"detail": "You are not a member of this team."}, status=403)

    client_id = settings.SLACK_CLIENT_ID
    redirect_uri = settings.SLACK_REDIRECT_URI
    if not client_id or not redirect_uri:
        return Response({"detail": "Slack OAuth is not configured."}, status=503)

    scopes = settings.SLACK_BOT_SCOPES
    signer = TimestampSigner(salt="slack-oauth-resolvemeq")
    state = signer.sign(f"{team.id}:{request.user.id}")
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    authorize_url = f"https://slack.com/oauth/v2/authorize?{params}"
    # SPA: fetch with Authorization header cannot follow redirect; return URL as JSON.
    if request.GET.get("format") == "json":
        return Response({"authorize_url": authorize_url})
    return HttpResponseRedirect(authorize_url)


@csrf_exempt
def slack_oauth_redirect(request):
    """
    Handles the OAuth redirect from Slack: exchanges code, links install to ResolveMeQ team from signed state.
    """
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")
    state = request.GET.get("state", "")
    signer = TimestampSigner(salt="slack-oauth-resolvemeq")
    try:
        raw = signer.unsign(state, max_age=60 * 15)
    except (BadSignature, SignatureExpired):
        return HttpResponse("Invalid or expired OAuth state.", status=400)
    parts = raw.split(":", 1)
    if len(parts) != 2:
        return HttpResponse("Malformed OAuth state.", status=400)
    team_id_str, user_id_str = parts
    team = Team.objects.filter(pk=team_id_str).first()
    installer = User.objects.filter(pk=user_id_str).first()
    if not team or not installer:
        return HttpResponse("Install session team or user no longer exists.", status=400)

    client_id = settings.SLACK_CLIENT_ID
    client_secret = settings.SLACK_CLIENT_SECRET
    redirect_uri = settings.SLACK_REDIRECT_URI
    token_url = "https://slack.com/api/oauth.v2.access"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(token_url, data=data, timeout=30)
    token_data = resp.json()

    if not token_data.get("ok"):
        return HttpResponse(f"Slack OAuth failed: {token_data.get('error', 'Unknown error')}", status=400)

    slack_workspace_id = token_data.get("team", {}).get("id")
    SlackToken.objects.update_or_create(
        team_id=slack_workspace_id,
        defaults={
            "access_token": token_data["access_token"],
            "bot_user_id": token_data.get("bot_user_id"),
            "resolvemeq_team": team,
            "installed_by": installer,
            "is_active": True,
        },
    )
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/settings/integrations?slack=connected")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def slack_integration_status(request):
    """Whether the current (or requested) team has an active Slack workspace install."""
    team_id = request.GET.get("team_id")
    if not team_id:
        prefs = getattr(request.user, "preferences", None)
        if prefs and prefs.active_team_id:
            team_id = str(prefs.active_team_id)
    if not team_id:
        return Response({"connected": False, "slack_team_id": None, "updated_at": None})
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return Response({"detail": "Team not found."}, status=404)
    if team.owner_id != request.user.pk and not team.members.filter(pk=request.user.pk).exists():
        return Response({"detail": "You are not a member of this team."}, status=403)
    inst = (
        SlackToken.objects.filter(resolvemeq_team=team, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return Response(
        {
            "connected": bool(inst),
            "slack_team_id": inst.team_id if inst else None,
            "updated_at": inst.updated_at.isoformat() if inst and inst.updated_at else None,
        }
    )


def verify_slack_request(request):
    """
    Verifies that incoming requests are genuinely from Slack using the signing secret.

    Checks the request timestamp and signature to prevent replay attacks and ensure authenticity.

    Args:
        request (HttpRequest): The incoming HTTP request from Slack.

    Returns:
        bool: True if the request is verified, False otherwise.
    """
    slack_signing_secret = settings.SLACK_SIGNING_SECRET
    
    # If no signing secret is configured, return False (not verified)
    if not slack_signing_secret:
        return False
    
    request_body = request.body
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    slack_signature = request.headers.get("X-Slack-Signature")

    # Protect against replay attacks
    if not timestamp or abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature or "")


def _slack_team_id_from_payload(payload: dict) -> str | None:
    """Slack workspace id from Events API envelope or interactive payload."""
    return payload.get("team_id") or (payload.get("team") or {}).get("id")


@csrf_exempt
def slack_events(request):
    """
    Handles incoming Slack event subscriptions and interactions.

    Verifies the request signature, responds to Slack's URL verification challenge,
    and processes other event types as needed.

    Methods:
        POST: Processes Slack events and URL verification.

    Returns:
        JsonResponse: For URL verification challenge.
        HttpResponse: 200 OK for other events, 403 Forbidden for failed verification, 400 Bad Request for invalid payloads.
    """
    if request.method == "POST":
        if not verify_slack_request(request):
            return HttpResponse(status=403)
        try:
            payload = json.loads(request.body)
        except Exception:
            return HttpResponse(status=400)
        # Handle Slack URL verification challenge
        if payload.get("type") == "url_verification":
            response = JsonResponse({"challenge": payload.get("challenge")})
            response['Content-Type'] = 'application/json; charset=utf-8'
            return response

        event = payload.get("event", {})
        slack_team_id = _slack_team_id_from_payload(payload)
        inst = slack_inst.get_installation_for_slack_team(slack_team_id)
        # Respond to app_mention events
        if event.get("type") == "app_mention":
            if inst:
                slack_inst.slack_api_post(
                    inst,
                    "chat.postMessage",
                    {"channel": event["channel"], "text": "Hello! You mentioned me :wave:"},
                )
        # Handle message events
        if event.get("type") == "message" and not event.get("bot_id"):
            if inst:
                slack_inst.slack_api_post(
                    inst,
                    "chat.postMessage",
                    {"channel": event["channel"], "text": "Hello from ResolveMeQ bot! :robot_face:"},
                )
        return HttpResponse(status=200, content_type='text/plain; charset=utf-8')
    return HttpResponse(status=405, content_type='text/plain; charset=utf-8')

def notify_user_ticket_created(slack_user_id, ticket_id, slack_team_id=None, installation=None):
    """DM the Slack user that a ticket was created."""
    inst = installation or slack_inst.get_installation_for_slack_team(slack_team_id)
    if not inst:
        return
    web = getattr(settings, "FRONTEND_URL", "https://app.resolvemeq.net").rstrip("/")
    resp = slack_inst.slack_api_post(
        inst,
        "chat.postMessage",
        {
            "channel": slack_user_id,
            "text": (
                f"🎟️ Ticket #{ticket_id} created successfully! We'll get back to you soon.\n"
                f"To attach a screenshot from your computer, use the web app ({web}/tickets) — the New ticket form supports image upload. "
                "You can also paste a public image URL in the Slack form next time."
            ),
        },
    )
    logger.info("Slack ticket created notification: %s", getattr(resp, "text", resp))


def notify_user_ticket_resolved(ticket):
    """DM the reporter on Slack when a ticket is resolved (Slack-backed users only)."""
    from tickets.models import Ticket

    if not isinstance(ticket, Ticket):
        ticket = (
            Ticket.objects.select_related("user", "team")
            .filter(ticket_id=ticket)
            .first()
        )
    if not ticket:
        return
    inst = slack_inst.get_installation_for_ticket(ticket)
    ch = slack_inst.slack_dm_channel_for_user(ticket.user)
    if not inst or not ch:
        return
    resp = slack_inst.slack_api_post(
        inst,
        "chat.postMessage",
        {"channel": ch, "text": f"🛠️ Your ticket #{ticket.ticket_id} is now marked as resolved."},
    )
    logger.info("Slack ticket resolved notification: %s", getattr(resp, "text", resp))


def _slack_modal_payload_view_submission(payload):
    """Shared handler for Slack `view_submission` (used by /slack/modal/ and /slack/actions/)."""
    if payload.get("type") != "view_submission":
        return JsonResponse({}, status=200)
    callback_id = payload.get("view", {}).get("callback_id")
    if callback_id == "clarify_modal":
        values = payload["view"]["state"]["values"]
        description = values["description_block"]["description"]["value"]
        issue_type = values["issue_type_block"]["issue_type"]["value"]
        user_id = payload["user"]["id"]
        slack_team_id = _slack_team_id_from_payload(payload)
        inst = slack_inst.get_installation_for_slack_team(slack_team_id)
        from tickets.models import Ticket, TicketInteraction

        qs = Ticket.objects.filter(
            user__username=user_id,
            status__in=["new", "open", "in_progress", "in-progress"],
        )
        if inst and inst.resolvemeq_team_id:
            qs = qs.filter(team_id=inst.resolvemeq_team_id)
        ticket = qs.order_by("-created_at").first()
        if not ticket:
            if inst:
                slack_inst.slack_api_post(
                    inst,
                    "chat.postMessage",
                    {
                        "channel": user_id,
                        "text": "Sorry, we couldn't find your ticket to clarify. Please try again or contact IT.",
                    },
                )
            return JsonResponse({"response_action": "clear"})
        try:
            ticket.description = description
            ticket.issue_type = issue_type
            ticket.save()
            TicketInteraction.objects.create(
                ticket=ticket,
                user=ticket.user,
                interaction_type="clarification",
                content=f"User clarified: Description='{description}', Issue Type='{issue_type}'",
            )
            from tickets.tasks import process_ticket_with_agent

            process_ticket_with_agent.delay(ticket.ticket_id)
        except Exception as e:
            if inst:
                slack_inst.slack_api_post(
                    inst,
                    "chat.postMessage",
                    {
                        "channel": user_id,
                        "text": f"Sorry, there was an error saving your clarification: {str(e)}",
                    },
                )
        return JsonResponse({"response_action": "clear"})
    if callback_id == "resolvemeq_modal":
        values = payload["view"]["state"]["values"]
        category = values["category_block"]["category"]["selected_option"]["value"]
        subject = (
            values.get("subject_block", {}).get("subject", {}).get("value") or ""
        ).strip()
        if not subject:
            return JsonResponse(
                {
                    "response_action": "errors",
                    "errors": {
                        "subject_block": "Enter a short subject (same as the web app).",
                    },
                }
            )
        urgency = values["urgency_block"]["urgency"]["selected_option"]["value"]
        description = (
            values.get("description_block", {}).get("description", {}).get("value") or ""
        )
        screenshot = values.get("screenshot_block", {}).get("screenshot", {}).get("value", "")
        user_id = payload["user"]["id"]
        slack_team_id = _slack_team_id_from_payload(payload)
        inst = slack_inst.get_installation_for_slack_team(slack_team_id)
        user, _ = slack_inst.get_or_create_slack_shadow_user(
            user_id,
            installation=inst,
            slack_user_payload=payload.get("user"),
        )
        team = inst.resolvemeq_team if inst else None
        from tickets.services import compose_issue_type, create_ticket_with_reporter

        ticket = create_ticket_with_reporter(
            user,
            team,
            issue_type=compose_issue_type(subject, urgency),
            description=description,
            screenshot=screenshot or None,
            category=category,
            status="new",
        )
        notify_user_ticket_created(
            user_id, ticket.ticket_id, installation=inst, slack_team_id=slack_team_id
        )
        return JsonResponse({"response_action": "clear"})
    if callback_id == "feedback_text_modal":
        ticket_id = payload["view"].get("private_metadata")
        feedback = payload["view"]["state"]["values"]["feedback_block"]["feedback_text"]["value"]
        user_id = payload["user"]["id"]
        slack_team_id = _slack_team_id_from_payload(payload)
        inst = slack_inst.get_installation_for_slack_team(slack_team_id)
        from tickets.models import Ticket, TicketInteraction
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
            TicketInteraction.objects.create(
                ticket=ticket,
                user=ticket.user,
                interaction_type="feedback",
                content=f"User feedback: {feedback}",
            )
            if inst:
                slack_inst.slack_api_post(
                    inst,
                    "chat.postMessage",
                    {
                        "channel": user_id,
                        "text": "Thank you for your feedback! Our IT team will review it shortly.",
                    },
                )
        except Exception:
            pass
        return JsonResponse({"response_action": "clear"})
    return JsonResponse({}, status=200)


@csrf_exempt
def slack_slash_command(request):
    """
    Handles the /resolvemeq slash command.
    - If no argument, opens a modal for ticket creation.
    - If 'status', shows the user's open tickets.

    Methods:
        POST: Processes slash command.

    Returns:
        JsonResponse or HttpResponse
    """
    if request.method == "POST":
        if not verify_slack_request(request):
            return HttpResponse(status=403)
        command = request.POST.get("command")
        text = request.POST.get("text", "").strip().lower()
        trigger_id = request.POST.get("trigger_id")
        user_id = request.POST.get("user_id")

        slack_team_id = request.POST.get("team_id")
        # Handle /resolvemeq status
        if command == "/resolvemeq" and text == "status":
            from tickets.models import Ticket

            tickets = Ticket.objects.filter(user__username=user_id).order_by("-created_at")
            if tickets.exists():
                status_lines = [
                    f"• Ticket #{t.ticket_id}: {t.issue_type} — {t.status.capitalize()}"
                    for t in tickets
                ]
                status_message = "*Your Tickets:*\n" + "\n".join(status_lines)
            else:
                status_message = "You have no tickets."
            return JsonResponse({"response_type": "ephemeral", "text": status_message})

        # Only handle /resolvemeq (open modal)
        if command == "/resolvemeq" and not text:
            from tickets.models import Ticket

            token_obj = slack_inst.get_installation_for_slack_team(slack_team_id)
            if not token_obj:
                return JsonResponse({"text": "Bot not authorized for this workspace."})
            # Same fields/order semantics as the web create form (see tickets.views.create_ticket).
            category_options = [
                {"text": {"type": "plain_text", "text": label}, "value": value}
                for value, label in Ticket.CATEGORY_CHOICES
            ]
            web_base = getattr(settings, "FRONTEND_URL", "https://app.resolvemeq.net").rstrip("/")
            modal_view = {
                "type": "modal",
                "callback_id": "resolvemeq_modal",
                "title": {"type": "plain_text", "text": "New IT Request"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"📎 *Screenshot from your device:* use the <{web_base}/tickets|ResolveMeQ web app> "
                                f"to upload images (recommended). Or paste a public image URL in the field below."
                            ),
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "category_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "category",
                            "placeholder": {"type": "plain_text", "text": "Select category"},
                            "options": category_options,
                        },
                        "label": {"type": "plain_text", "text": "Category"},
                    },
                    {
                        "type": "input",
                        "block_id": "subject_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "subject",
                            "max_length": 100,
                            "placeholder": {"type": "plain_text", "text": "Brief summary of the issue"},
                        },
                        "label": {"type": "plain_text", "text": "Subject"},
                    },
                    {
                        "type": "input",
                        "block_id": "urgency_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "urgency",
                            "placeholder": {"type": "plain_text", "text": "Select urgency"},
                            "options": [
                                {"text": {"type": "plain_text", "text": "Low"}, "value": "low"},
                                {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                                {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                            ],
                        },
                        "label": {"type": "plain_text", "text": "Urgency"},
                    },
                    {
                        "type": "input",
                        "block_id": "description_block",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "description",
                            "multiline": True,
                            "placeholder": {"type": "plain_text", "text": "Additional details (optional)"},
                        },
                        "label": {"type": "plain_text", "text": "Description"},
                    },
                    {
                        "type": "input",
                        "block_id": "screenshot_block",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "screenshot",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Image link if hosted elsewhere (optional)",
                            },
                        },
                        "label": {"type": "plain_text", "text": "Screenshot link (optional)"},
                    },
                ],
            }
            # Open modal
            headers = {
                "Authorization": f"Bearer {token_obj.access_token}",
                "Content-Type": "application/json",
            }
            data = {
                "trigger_id": trigger_id,
                "view": modal_view,
            }
            requests.post("https://slack.com/api/views.open", headers=headers, json=data, timeout=30)
            return HttpResponse()  # Slack expects 200 OK
        return JsonResponse({"text": "Unknown command."})
    return HttpResponse(status=405)

@csrf_exempt
def slack_modal_submission(request):
    """
    Handles modal submissions from Slack and creates a ticket in the backend.
    Also handles clarification modals for missing info.
    """
    if request.method == "POST":
        if not verify_slack_request(request):
            return HttpResponse(status=403)
        payload = json.loads(request.POST.get("payload", "{}"))
        return _slack_modal_payload_view_submission(payload)
    return HttpResponse(status=405)


# --- Unified Slack Interactive Endpoint ---
@method_decorator(csrf_exempt, name="dispatch")
class SlackInteractiveActionView(View):
    """
    Unified handler for all Slack interactive events (buttons, selects, modals).
    Set your Slack Interactivity Request URL to /api/integrations/slack/actions/
    """
    def dispatch(self, request, *args, **kwargs):
        from django.http import HttpResponseNotAllowed
        if request.method.lower() != 'post':
            return HttpResponseNotAllowed(['POST'])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        if not verify_slack_request(request):
            logger.warning("Slack interactive POST forbidden: signature verification failed. Headers: %s, Body: %s", dict(request.headers), request.body)
            return HttpResponse(status=403)
        try:
            payload = json.loads(request.POST.get("payload", "{}"))
        except Exception:
            return HttpResponse(status=400)
        payload_type = payload.get("type")
        slack_team_id = _slack_team_id_from_payload(payload)
        inst_workspace = slack_inst.get_installation_for_slack_team(slack_team_id)
        # Handle block_actions (button/select)
        if payload_type == "block_actions":
            actions = payload.get("actions", [])
            user_id = payload.get("user", {}).get("id")
            response_url = payload.get("response_url")
            thread_ts = payload.get("message", {}).get("ts")
            if actions:
                action = actions[0]
                action_id = action.get("action_id")
                value = action.get("value", "")
                # Handle "Ask Again"
                if action_id == "ask_again" and value.startswith("ask_again_"):
                    ticket_id = value.replace("ask_again_", "")
                    from tickets.tasks import process_ticket_with_agent
                    from tickets.models import Ticket as TicketModel

                    t = (
                        TicketModel.objects.select_related("team")
                        .filter(ticket_id=ticket_id)
                        .first()
                    )
                    inst_act = slack_inst.get_installation_for_ticket(t) if t else inst_workspace
                    if inst_act:
                        progress_msg = {
                            "channel": user_id,
                            "text": f"🔄 Working on Ticket #{ticket_id}...",
                            "thread_ts": thread_ts or None,
                        }
                        resp = slack_inst.slack_api_post(inst_act, "chat.postMessage", progress_msg)
                        if resp and resp.ok:
                            progress_data = resp.json()
                            thread_ts = progress_data.get("ts", thread_ts)
                    # Pass thread_ts to Celery task
                    process_ticket_with_agent.delay(ticket_id, thread_ts)
                    requests.post(response_url, json={
                        "replace_original": False,
                        "text": f"🔄 Ticket #{ticket_id} is being reprocessed by the agent."
                    })
                    return HttpResponse()
                # Handle "Mark as Resolved"
                elif action_id == "resolve_ticket" and value.startswith("resolve_"):
                    ticket_id = value.replace("resolve_", "")
                    from tickets.models import Ticket
                    try:
                        ticket = Ticket.objects.get(ticket_id=ticket_id)
                        ticket.status = "resolved"
                        ticket.save()
                        notify_user_ticket_resolved(ticket)
                        # Prompt for feedback
                        if inst_workspace:
                            feedback_blocks = [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"How helpful was the agent's response for Ticket #{ticket_id}?",
                                    },
                                },
                                {
                                    "type": "actions",
                                    "elements": [
                                        {
                                            "type": "button",
                                            "text": {"type": "plain_text", "text": "👍 Helpful"},
                                            "value": f"feedback_positive_{ticket_id}",
                                            "action_id": "feedback_positive",
                                        },
                                        {
                                            "type": "button",
                                            "text": {"type": "plain_text", "text": "👎 Not Helpful"},
                                            "value": f"feedback_negative_{ticket_id}",
                                            "action_id": "feedback_negative",
                                        },
                                    ],
                                },
                            ]
                            slack_inst.slack_api_post(
                                inst_workspace,
                                "chat.postMessage",
                                {
                                    "channel": user_id,
                                    "blocks": feedback_blocks,
                                    "text": "Please rate the agent's response.",
                                },
                            )
                        requests.post(response_url, json={
                            "replace_original": False,
                            "text": f"✅ Ticket #{ticket_id} marked as resolved."
                        })
                    except Ticket.DoesNotExist:
                        requests.post(response_url, json={
                            "replace_original": False,
                            "text": f"❌ Ticket #{ticket_id} not found."
                        })
                    return HttpResponse()
                # Handle feedback buttons
                elif action_id in ("feedback_positive", "feedback_negative"):
                    feedback = "helpful" if action_id == "feedback_positive" else "not helpful"
                    ticket_id = value.split("_")[-1]
                    # Log feedback as TicketInteraction
                    from tickets.models import Ticket, TicketInteraction
                    try:
                        ticket = Ticket.objects.get(ticket_id=ticket_id)
                        TicketInteraction.objects.create(
                            ticket=ticket,
                            user=ticket.user,
                            interaction_type="feedback",
                            content=f"User marked agent response as: {feedback}"
                        )
                        # Sync to knowledge base if resolved and has agent response
                        ticket.sync_to_knowledge_base()
                    except Exception:
                        pass
                    requests.post(response_url, json={
                        "replace_original": False,
                        "text": f"Thank you for your feedback on Ticket #{ticket_id}: *{feedback}*."
                    })
                    return HttpResponse()
                # Handle clarification prompt
                elif action_id == "clarify_ticket" and value.startswith("clarify_"):
                    ticket_id = value.replace("clarify_", "")
                    # Open a modal for the user to provide more info
                    if inst_workspace:
                        modal_view = {
                            "type": "modal",
                            "callback_id": "clarify_modal",
                            "title": {"type": "plain_text", "text": "Provide More Info"},
                            "submit": {"type": "plain_text", "text": "Submit"},
                            "close": {"type": "plain_text", "text": "Cancel"},
                            "private_metadata": ticket_id,
                            "blocks": [
                                {
                                    "type": "input",
                                    "block_id": "description_block",
                                    "element": {
                                        "type": "plain_text_input",
                                        "action_id": "description",
                                        "multiline": True,
                                    },
                                    "label": {"type": "plain_text", "text": "Description (required)"},
                                },
                                {
                                    "type": "input",
                                    "block_id": "issue_type_block",
                                    "element": {
                                        "type": "plain_text_input",
                                        "action_id": "issue_type",
                                    },
                                    "label": {"type": "plain_text", "text": "Issue Type (required)"},
                                },
                            ],
                        }
                        trigger_id = payload.get("trigger_id")
                        data = {
                            "trigger_id": trigger_id,
                            "view": modal_view,
                        }
                        slack_inst.slack_api_post(inst_workspace, "views.open", data)
                    return HttpResponse()
                elif action_id == "cancel_ticket" and value.startswith("cancel_"):
                    ticket_id = value.replace("cancel_", "")
                    requests.post(response_url, json={
                        "replace_original": False,
                        "text": f"❌ Ticket #{ticket_id} update cancelled."
                    })
                    return HttpResponse()
                # Handle "Escalate" action
                elif action_id == "escalate_ticket" and value.startswith("escalate_"):
                    ticket_id = value.replace("escalate_", "")
                    from tickets.models import Ticket, TicketInteraction
                    try:
                        ticket = Ticket.objects.get(ticket_id=ticket_id)
                        TicketInteraction.objects.create(
                            ticket=ticket,
                            user=ticket.user,
                            interaction_type="user_message",
                            content="User requested escalation via Slack."
                        )
                        # Optionally, notify admins or escalation channel here
                    except Exception:
                        pass
                    requests.post(response_url, json={
                        "replace_original": False,
                        "text": f"🚨 Ticket #{ticket_id} has been escalated. An IT admin will review it shortly."
                    })
                    return HttpResponse()
                # Handle feedback text button
                elif action_id == "feedback_text" and value.startswith("feedback_"):
                    ticket_id = value.replace("feedback_", "")
                    if inst_workspace:
                        modal_view = {
                            "type": "modal",
                            "callback_id": "feedback_text_modal",
                            "title": {"type": "plain_text", "text": "Provide Feedback"},
                            "submit": {"type": "plain_text", "text": "Send"},
                            "close": {"type": "plain_text", "text": "Cancel"},
                            "private_metadata": ticket_id,
                            "blocks": [
                                {
                                    "type": "input",
                                    "block_id": "feedback_block",
                                    "element": {
                                        "type": "plain_text_input",
                                        "action_id": "feedback_text",
                                        "multiline": True,
                                        "placeholder": {"type": "plain_text", "text": "Type your feedback or describe your issue in detail..."}
                                    },
                                    "label": {"type": "plain_text", "text": "Your Feedback (required)"},
                                }
                            ]
                        }
                        trigger_id = payload.get("trigger_id")
                        data = {
                            "trigger_id": trigger_id,
                            "view": modal_view,
                        }
                        slack_inst.slack_api_post(inst_workspace, "views.open", data)
                    return HttpResponse()
        elif payload_type == "view_submission":
            return _slack_modal_payload_view_submission(payload)
        # Always return 200 OK for unknown or unhandled payloads
        return HttpResponse(status=200)


def _slack_install_and_dm_for_ticket_id(ticket_id):
    """Resolve bot installation + DM channel id for a ticket's reporter (Slack shadow users)."""
    from tickets.models import Ticket

    ticket = (
        Ticket.objects.select_related("user", "team")
        .filter(ticket_id=ticket_id)
        .first()
    )
    if not ticket:
        return None, None
    inst = slack_inst.get_installation_for_ticket(ticket)
    slack_user_or_channel = slack_inst.slack_dm_channel_for_user(ticket.user)
    if not inst or not slack_user_or_channel:
        return inst, slack_user_or_channel

    # Hard safety normalization for legacy lowercase Slack IDs.
    if (
        len(slack_user_or_channel) >= 9
        and slack_user_or_channel[0].upper() in ("U", "W")
        and slack_user_or_channel[1:].replace("_", "").isalnum()
    ):
        slack_user_or_channel = slack_user_or_channel.upper()

    # Prefer a real DM channel id. Posting directly to a user id can return channel_not_found
    # depending on workspace/app configuration.
    if slack_user_or_channel.startswith(("D", "C", "G")):
        return inst, slack_user_or_channel

    dm_resp = slack_inst.slack_api_post(
        inst,
        "conversations.open",
        {"users": slack_user_or_channel},
    )
    if not dm_resp:
        logger.warning("Slack DM open failed for ticket %s: empty response", ticket_id)
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
        ticket_id,
        slack_user_or_channel,
        dm_data.get("error") or getattr(dm_resp, "text", "unknown_error"),
    )
    # Fallback to previous behavior; some workspaces allow posting with user id.
    return inst, slack_user_or_channel


def _slack_truncate_mrkdwn(text: str, max_len: int = 2800) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rsplit(" ", 1)[0] + "…"


def notify_user_agent_response(user_id, ticket_id, agent_response, thread_ts=None):
    """
    Sends the agent's analysis and recommendations to the user via Slack DM, with interactive buttons.
    Args:
        user_id (str): Slack user ID or UUID.
        ticket_id (int): Ticket ID.
        agent_response (dict): The response from the agent (should be a dict, not JSON string).
        thread_ts (str, optional): Slack thread timestamp to reply in thread.
    """
    import json

    inst, slack_channel = _slack_install_and_dm_for_ticket_id(ticket_id)
    if not inst or not slack_channel:
        logger.warning(
            "Slack agent summary skipped (ticket_id=%s): no installation or DM channel for reporter",
            ticket_id,
        )
        return
    # Format the agent response for Slack
    if isinstance(agent_response, str):
        try:
            agent_response = json.loads(agent_response)
        except Exception:
            agent_response = {"analysis": {}, "recommendations": {}}
    if not isinstance(agent_response, dict):
        agent_response = {"analysis": {}, "recommendations": {}}
    analysis = agent_response.get("analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}
    recommendations = agent_response.get("recommendations") or {}
    if not isinstance(recommendations, dict):
        recommendations = {}
    solution = agent_response.get("solution") or {}
    if not isinstance(solution, dict):
        solution = {}
    reasoning = (agent_response.get("reasoning") or "").strip()
    confidence = agent_response.get("confidence")

    def _clean_scalar(v):
        if v is None:
            return None
        if isinstance(v, str):
            t = v.strip()
            if not t or t.lower() in {"none", "n/a", "unknown", "null"}:
                return None
            return t
        return str(v)

    def _clean_list(v, limit=8):
        if not isinstance(v, list):
            return []
        out = []
        for item in v:
            text = _clean_scalar(item)
            if text:
                out.append(text)
            if len(out) >= limit:
                break
        return out

    # Build Slack blocks with readable sections instead of raw key/value dumps.
    header = f"🤖 *AI update for ticket #{ticket_id}*"
    if confidence is not None:
        try:
            header += f" _(confidence {float(confidence):.0%})_"
        except (TypeError, ValueError):
            pass
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": header}}]

    overview_fields = []
    for label, key in [
        ("Category", "category"),
        ("Severity", "severity"),
        ("Complexity", "complexity"),
        ("Priority", "priority"),
        ("Est. Resolution Time", "estimated_resolution_time"),
    ]:
        value = _clean_scalar(analysis.get(key))
        if value:
            overview_fields.append({"type": "mrkdwn", "text": f"*{label}*\n{value}"})
    if overview_fields:
        blocks.append({"type": "section", "fields": overview_fields[:10]})

    summary_text = _clean_scalar(reasoning) or _clean_scalar(analysis.get("summary"))
    if summary_text:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": _slack_truncate_mrkdwn(f"*What I found*\n{summary_text}", max_len=1200)},
            }
        )

    required_skills = _clean_list(analysis.get("required_skills"), limit=6)
    suggested_tags = _clean_list(analysis.get("suggested_tags"), limit=8)
    if required_skills or suggested_tags:
        lines = []
        if required_skills:
            lines.append(f"*Required skills:* {', '.join(required_skills)}")
        if suggested_tags:
            lines.append(f"*Suggested tags:* {', '.join(suggested_tags)}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": _slack_truncate_mrkdwn('\n'.join(lines), max_len=1000)}})

    immediate_actions = _clean_list(solution.get("immediate_actions"), limit=6) or _clean_list(
        recommendations.get("immediate_actions"), limit=6
    )
    if immediate_actions:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _slack_truncate_mrkdwn("*Try this first*\n" + "\n".join(f"• {x}" for x in immediate_actions), max_len=1200),
                },
            }
        )

    resolution_steps = _clean_list(solution.get("steps"), limit=7) or _clean_list(recommendations.get("resolution_steps"), limit=7)
    if resolution_steps:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _slack_truncate_mrkdwn(
                        "*Recommended steps*\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(resolution_steps)),
                        max_len=1400,
                    ),
                },
            }
        )

    preventive = _clean_list(solution.get("preventive_measures"), limit=5) or _clean_list(
        recommendations.get("preventive_measures"), limit=5
    )
    if preventive:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _slack_truncate_mrkdwn("*Prevention tips*\n" + "\n".join(f"• {x}" for x in preventive), max_len=1000),
                },
            }
        )

    blocks.append({"type": "divider"})
    # Add interactive buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Mark as Resolved"},
                "style": "primary",
                "value": f"resolve_{ticket_id}",
                "action_id": "resolve_ticket"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✏️ Clarify"},
                "value": f"clarify_{ticket_id}",
                "action_id": "clarify_ticket"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🚨 Escalate"},
                "style": "danger",
                "value": f"escalate_{ticket_id}",
                "action_id": "escalate_ticket"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "💬 Feedback"},
                "value": f"feedback_{ticket_id}",
                "action_id": "feedback_text"
            }
        ]
    })
    payload = {
        "channel": slack_channel,
        "blocks": blocks,
        "text": f"Agent response for Ticket #{ticket_id}",
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    try:
        data = resp.json() if resp else {}
    except Exception:
        data = {}
    if data.get("ok"):
        logger.info("Sent agent response to Slack (ticket=%s, channel=%s)", ticket_id, slack_channel)
    else:
        logger.warning(
            "Failed to send agent response to Slack (ticket=%s, channel=%s): %s",
            ticket_id,
            slack_channel,
            data.get("error") or getattr(resp, "text", resp),
        )

def notify_user_auto_resolution(user_id, ticket_id, params):
    """
    Notify user that their ticket was automatically resolved.
    """
    inst, slack_channel = _slack_install_and_dm_for_ticket_id(ticket_id)
    if not inst or not slack_channel:
        return
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"✅ *Ticket #{ticket_id} Auto-Resolved*\n\nYour issue has been automatically resolved by our AI agent!"
            }
        }
    ]
    
    # Add resolution steps if available
    resolution_steps = params.get('resolution_steps', [])
    if resolution_steps:
        steps_text = "\n".join([f"• {step}" for step in resolution_steps])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Resolution Steps:*\n{steps_text}"
            }
        })
    
    # Add reasoning
    reasoning = params.get('reasoning', '')
    if reasoning:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Why this solution:* {reasoning}"
            }
        })
    
    # Add feedback buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Issue Resolved"},
                "style": "primary",
                "value": f"confirm_resolved_{ticket_id}",
                "action_id": "confirm_resolution"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Still Having Issues"},
                "style": "danger",
                "value": f"reopen_{ticket_id}",
                "action_id": "reopen_ticket"
            }
        ]
    })
    
    payload = {
        "channel": slack_channel,
        "blocks": blocks,
        "text": f"Ticket #{ticket_id} has been auto-resolved",
    }
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    logger.info("Sent auto-resolution notification: %s", getattr(resp, "text", resp))

def notify_escalation(user_id, ticket_id, params):
    """
    Notify user that their ticket has been escalated.
    """
    inst, slack_channel = _slack_install_and_dm_for_ticket_id(ticket_id)
    if not inst or not slack_channel:
        return
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *Ticket #{ticket_id} Escalated*\n\nYour issue has been escalated to our {params.get('suggested_team', 'support team')} for specialized assistance."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Reason:* {params.get('escalation_reason', 'Complex issue requiring human expertise')}\n*Priority:* {params.get('priority', 'medium').upper()}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "A human support agent will review your case and contact you shortly."
            }
        }
    ]
    
    payload = {
        "channel": slack_channel,
        "blocks": blocks,
        "text": f"Ticket #{ticket_id} has been escalated",
    }
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    logger.info("Sent escalation notification: %s", getattr(resp, "text", resp))


def notify_support_escalation_slack(ticket, params):
    """
    Post escalated ticket to a dedicated Slack channel for support visibility.
    Requires SLACK_ESCALATION_CHANNEL to be set (channel ID, e.g. C01234ABCD).
    """
    from django.conf import settings
    channel = getattr(settings, "SLACK_ESCALATION_CHANNEL", "") or ""
    if not channel:
        return
    inst = slack_inst.get_installation_for_ticket(ticket)
    if not inst:
        return
    user_name = getattr(ticket.user, "name", None) or getattr(ticket.user, "username", None) or str(ticket.user.id)
    if hasattr(ticket.user, "get_full_name") and ticket.user.get_full_name():
        user_name = ticket.user.get_full_name()
    elif hasattr(ticket.user, "email"):
        user_name = ticket.user.email or user_name
    desc = (ticket.description or "")[:300]
    if len((ticket.description or "")) > 300:
        desc += "..."
    summary = params.get("conversation_summary", "")
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *New Escalation – Ticket #{ticket.ticket_id}*\n\n*From:* {user_name}\n*Subject:* {ticket.issue_type or 'No title'}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{desc or '_No description_'}"
            }
        },
    ]
    if summary:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Conversation context:*\n{summary[:400]}{'...' if len(summary) > 400 else ''}"
            }
        })
    handoff = (params.get("handoff_summary") or params.get("handoff_text") or "").strip()
    if handoff:
        h = handoff[:500]
        if len(handoff) > 500:
            h += "..."
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Handoff:*\n{h}"},
        })
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Ticket"},
                "url": f"{getattr(settings, 'FRONTEND_URL', 'https://app.resolvemeq.net')}/tickets?highlight={ticket.ticket_id}",
            }
        ]
    })
    payload = {
        "channel": channel,
        "blocks": blocks,
        "text": f"Ticket #{ticket.ticket_id} escalated – {ticket.issue_type or 'Support needed'}",
    }
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    if resp:
        logger.info("Sent support escalation notification: %s", resp.text)
    else:
        logger.warning("Failed to post escalation to Slack")


def request_clarification_from_user(user_id, ticket_id, params):
    """
    Request clarification from user via Slack.
    """
    inst, slack_channel = _slack_install_and_dm_for_ticket_id(ticket_id)
    if not inst or not slack_channel:
        return
    
    questions = params.get('questions', [])
    questions_text = "\n".join([f"• {q}" for q in questions])
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❓ *Need More Information - Ticket #{ticket_id}*\n\nTo provide you with the best solution, I need some additional details:"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": questions_text
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "💬 Provide Details"},
                    "style": "primary",
                    "value": f"clarify_{ticket_id}",
                    "action_id": "clarify_ticket"
                }
            ]
        }
    ]
    
    payload = {
        "channel": slack_channel,
        "blocks": blocks,
        "text": f"Need clarification for Ticket #{ticket_id}",
    }
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    try:
        data = resp.json() if resp else {}
    except Exception:
        data = {}
    if data.get("ok"):
        logger.info("Sent clarification request for ticket %s to channel %s", ticket_id, slack_channel)
    else:
        logger.warning(
            "Clarification request failed for ticket %s (channel=%s): %s",
            ticket_id,
            slack_channel,
            data.get("error") or getattr(resp, "text", resp),
        )

def send_solution_with_followup(user_id, ticket_id, params):
    """
    Send solution to user with automatic follow-up scheduled.
    """
    inst, slack_channel = _slack_install_and_dm_for_ticket_id(ticket_id)
    if not inst or not slack_channel:
        return
    
    solution_steps = params.get('solution_steps', [])
    steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(solution_steps)])
    
    followup_time = params.get('followup_time')
    confidence = params.get('confidence_level', 0.0)
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔧 *Solution for Ticket #{ticket_id}*\n\nI've found a likely solution (confidence: {confidence:.0%}):"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Steps to resolve:*\n{steps_text}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"I'll check back with you in a few minutes to see if this resolved your issue."
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ This Fixed It"},
                    "style": "primary",
                    "value": f"resolved_{ticket_id}",
                    "action_id": "mark_resolved"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Still Not Working"},
                    "style": "danger",
                    "value": f"escalate_{ticket_id}",
                    "action_id": "escalate_ticket"
                }
            ]
        }
    ]
    
    payload = {
        "channel": slack_channel,
        "blocks": blocks,
        "text": f"Solution for Ticket #{ticket_id}",
    }
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    logger.info("Sent solution with follow-up: %s", getattr(resp, "text", resp))
