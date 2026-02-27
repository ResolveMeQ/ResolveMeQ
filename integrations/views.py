"""
Slack integration views for OAuth, events, slash commands, and interactive actions.
Handles Slack authentication, event verification, ticket creation, notifications, and more.
"""

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import HttpResponse
import hmac
import hashlib
import time
import logging
from .models import SlackToken
import requests
from django.views import View
from django.utils.decorators import method_decorator
from base.models import User

@csrf_exempt
def slack_oauth_redirect(request):
    """
    Handles the OAuth redirect from Slack.

    Exchanges the temporary OAuth code provided by Slack for an access token.
    On success, stores the access token securely in the database for future API calls.

    Query Parameters:
        code (str): The temporary OAuth code sent by Slack.

    Returns:
        HttpResponse: "Slack app connected!" on success, or error details on failure.
    """
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")

    client_id = settings.SLACK_CLIENT_ID
    client_secret = settings.SLACK_CLIENT_SECRET
    redirect_uri = settings.SLACK_REDIRECT_URI

    # Exchange code for access token
    token_url = "https://slack.com/api/oauth.v2.access"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(token_url, data=data)
    token_data = resp.json()

    if not token_data.get("ok"):
        return HttpResponse(f"Slack OAuth failed: {token_data.get('error', 'Unknown error')}", status=400)

    # Save access_token and bot_user_id
    SlackToken.objects.create(
        access_token=token_data["access_token"],
        team_id=token_data.get("team", {}).get("id"),
        bot_user_id=token_data.get("bot_user_id"),
    )
    return HttpResponse("Slack app connected!")

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
        # Respond to app_mention events
        if event.get("type") == "app_mention":
            token_obj = SlackToken.objects.order_by("-created_at").first()
            if token_obj:
                headers = {
                    "Authorization": f"Bearer {token_obj.access_token}",
                    "Content-Type": "application/json",
                }
                reply_data = {
                    "channel": event["channel"],
                    "text": "Hello! You mentioned me :wave:"
                }
                requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=reply_data)
        # Handle message events
        if event.get("type") == "message" and not event.get("bot_id"):
            # Get the latest bot token
            token_obj = SlackToken.objects.order_by("-created_at").first()
            if token_obj:
                headers = {
                    "Authorization": f"Bearer {token_obj.access_token}",
                    "Content-Type": "application/json",
                }
                reply_data = {
                    "channel": event["channel"],
                    "text": "Hello from ResolveMeQ bot! :robot_face:"
                }
                requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=reply_data)
        return HttpResponse(status=200, content_type='text/plain; charset=utf-8')
    return HttpResponse(status=405, content_type='text/plain; charset=utf-8')

def notify_user_ticket_created(user_id, ticket_id):
    """
    Sends a Slack DM to the user with the ticket ID after ticket creation.

    Args:
        user_id (str): Slack user ID.
        ticket_id (int): Ticket ID.
    """
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if token_obj:
        headers = {
            "Authorization": f"Bearer {token_obj.access_token}",
            "Content-Type": "application/json",
        }
        reply_data = {
            "channel": user_id,
            "text": (
                f"🎟️ Ticket #{ticket_id} created successfully! We’ll get back to you soon.\n"
                "If you have a screenshot, please upload it here and mention your ticket number."
            ),
        }
        resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=reply_data)
        print("Slack ticket created notification:", resp.text)

def notify_user_ticket_resolved(user_id, ticket_id):
    """
    Sends a Slack DM to the user when their ticket is marked as resolved.

    Args:
        user_id (str): Slack user ID.
        ticket_id (int): Ticket ID.
    """
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if token_obj:
        headers = {
            "Authorization": f"Bearer {token_obj.access_token}",
            "Content-Type": "application/json",
        }
        reply_data = {
            "channel": user_id,
            "text": f"🛠️ Your ticket #{ticket_id} is now marked as resolved.",
        }
        resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=reply_data)
        print("Slack ticket resolved notification:", resp.text)

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

        # Handle /resolvemeq status
        if command == "/resolvemeq" and text == "status":
            from tickets.models import Ticket
            tickets = Ticket.objects.filter(user_id=user_id).order_by("-created_at")
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
            token_obj = SlackToken.objects.order_by("-created_at").first()
            if not token_obj:
                return JsonResponse({"text": "Bot not authorized."})
            # Build modal view
            modal_view = {
                "type": "modal",
                "callback_id": "resolvemeq_modal",
                "title": {"type": "plain_text", "text": "New IT Request"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "category_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "category",
                            "placeholder": {"type": "plain_text", "text": "Select category"},
                            "options": [
                                {"text": {"type": "plain_text", "text": "Wi-Fi"}, "value": "wifi"},
                                {"text": {"type": "plain_text", "text": "Laptop"}, "value": "laptop"},
                                {"text": {"type": "plain_text", "text": "VPN"}, "value": "vpn"},
                                {"text": {"type": "plain_text", "text": "Printer"}, "value": "printer"},
                                {"text": {"type": "plain_text", "text": "Email"}, "value": "email"},
                                {"text": {"type": "plain_text", "text": "Software"}, "value": "software"},
                                {"text": {"type": "plain_text", "text": "Hardware"}, "value": "hardware"},
                                {"text": {"type": "plain_text", "text": "Network"}, "value": "network"},
                                {"text": {"type": "plain_text", "text": "Account"}, "value": "account"},
                                {"text": {"type": "plain_text", "text": "Access"}, "value": "access"},
                                {"text": {"type": "plain_text", "text": "Phone"}, "value": "phone"},
                                {"text": {"type": "plain_text", "text": "Server"}, "value": "server"},
                                {"text": {"type": "plain_text", "text": "Security"}, "value": "security"},
                                {"text": {"type": "plain_text", "text": "Cloud"}, "value": "cloud"},
                                {"text": {"type": "plain_text", "text": "Storage"}, "value": "storage"},
                                {"text": {"type": "plain_text", "text": "Other"}, "value": "other"},
                            ],
                        },
                        "label": {"type": "plain_text", "text": "Service Category"},
                    },
                    {
                        "type": "input",
                        "block_id": "issue_type_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "issue_type",
                            "placeholder": {"type": "plain_text", "text": "Select issue type"},
                            "options": [
                                {"text": {"type": "plain_text", "text": "Report"}, "value": "report"},
                                {"text": {"type": "plain_text", "text": "Status"}, "value": "status"},
                                {"text": {"type": "plain_text", "text": "Escalate"}, "value": "escalate"},
                            ],
                        },
                        "label": {"type": "plain_text", "text": "Issue Type"},
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
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "description",
                            "multiline": True,
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
                            "placeholder": {"type": "plain_text", "text": "Paste screenshot URL (optional)"},
                        },
                        "label": {"type": "plain_text", "text": "Screenshot URL"},
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
            requests.post("https://slack.com/api/views.open", headers=headers, json=data)
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
        # Handle clarification modal
        if payload.get("type") == "view_submission" and payload.get("view", {}).get("callback_id") == "clarify_modal":
            values = payload["view"]["state"]["values"]
            description = values["description_block"]["description"]["value"]
            issue_type = values["issue_type_block"]["issue_type"]["value"]
            user_id = payload["user"]["id"]
            from tickets.models import Ticket, TicketInteraction
            ticket = Ticket.objects.filter(user__user_id=user_id, status__in=["new", "in-progress"]).order_by("-created_at").first()
            if not ticket:
                # Notify user in Slack if ticket not found
                token_obj = SlackToken.objects.order_by("-created_at").first()
                if token_obj:
                    headers = {
                        "Authorization": f"Bearer {token_obj.access_token}",
                        "Content-Type": "application/json",
                    }
                    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                        "channel": user_id,
                        "text": "Sorry, we couldn't find your ticket to clarify. Please try again or contact IT."
                    })
                return JsonResponse({"response_action": "clear"})
            try:
                ticket.description = description
                ticket.issue_type = issue_type
                ticket.save()
                # Log clarification interaction
                TicketInteraction.objects.create(
                    ticket=ticket,
                    user=ticket.user,
                    interaction_type="clarification",
                    content=f"User clarified: Description='{description}', Issue Type='{issue_type}'"
                )
                # Optionally, reprocess with agent
                from tickets.tasks import process_ticket_with_agent
                process_ticket_with_agent.delay(ticket.ticket_id)
            except Exception as e:
                # Notify user in Slack if clarification fails
                token_obj = SlackToken.objects.order_by("-created_at").first()
                if token_obj:
                    headers = {
                        "Authorization": f"Bearer {token_obj.access_token}",
                        "Content-Type": "application/json",
                    }
                    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                        "channel": user_id,
                        "text": f"Sorry, there was an error saving your clarification: {str(e)}"
                    })
            return JsonResponse({"response_action": "clear"})
        if payload.get("type") == "view_submission" and payload.get("view", {}).get("callback_id") == "resolvemeq_modal":
            values = payload["view"]["state"]["values"]
            category = values["category_block"]["category"]["selected_option"]["value"]
            issue_type = values["issue_type_block"]["issue_type"]["selected_option"]["value"]
            urgency = values["urgency_block"]["urgency"]["selected_option"]["value"]
            description = values["description_block"]["description"]["value"]
            screenshot = values.get("screenshot_block", {}).get("screenshot", {}).get("value", "")
            user_id = payload["user"]["id"]
            from tickets.models import Ticket, TicketInteraction
            user, _ = User.objects.get_or_create(username=user_id, defaults={"email": f"{user_id}@slack.local"})
            ticket = Ticket.objects.create(
                user=user,
                issue_type=f"{issue_type} ({urgency})",
                status="new",
                description=description,
                screenshot=screenshot,
                category=category,
            )
            # Log ticket creation as an interaction
            TicketInteraction.objects.create(
                ticket=ticket,
                user=user,
                interaction_type="user_message",
                content=f"Ticket created: {description}"
            )
            notify_user_ticket_created(user_id, ticket.ticket_id)
            return JsonResponse({"response_action": "clear"})
        if payload.get("type") == "view_submission" and payload.get("view", {}).get("callback_id") == "feedback_text_modal":
            ticket_id = payload["view"].get("private_metadata")
            feedback = payload["view"]["state"]["values"]["feedback_block"]["feedback_text"]["value"]
            user_id = payload["user"]["id"]
            from tickets.models import Ticket, TicketInteraction
            try:
                ticket = Ticket.objects.get(ticket_id=ticket_id)
                TicketInteraction.objects.create(
                    ticket=ticket,
                    user=ticket.user,
                    interaction_type="feedback",
                    content=f"User feedback: {feedback}"
                )
                # Send confirmation to user
                token_obj = SlackToken.objects.order_by("-created_at").first()
                if token_obj:
                    headers = {
                        "Authorization": f"Bearer {token_obj.access_token}",
                        "Content-Type": "application/json",
                    }
                    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                        "channel": user_id,
                        "text": "Thank you for your feedback! Our IT team will review it shortly."
                    })
                # (Optional) Notify IT staff (e.g., send to a channel)
                # requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                #     "channel": "#it-support",
                #     "text": f"New feedback for Ticket #{ticket_id}: {feedback}"
                # })
            except Exception:
                pass
            return JsonResponse({"response_action": "clear"})
        return JsonResponse({}, status=200)
    return HttpResponse(status=405)

# --- Unified Slack Interactive Endpoint ---
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

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
                    # Post progress update in thread
                    token_obj = SlackToken.objects.order_by("-created_at").first()
                    if token_obj:
                        headers = {
                            "Authorization": f"Bearer {token_obj.access_token}",
                            "Content-Type": "application/json",
                        }
                        progress_msg = {
                            "channel": user_id,
                            "text": f"🔄 Working on Ticket #{ticket_id}...",
                            "thread_ts": thread_ts or None
                        }
                        resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=progress_msg)
                        if resp.ok:
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
                        notify_user_ticket_resolved(user_id, ticket_id)
                        # Prompt for feedback
                        token_obj = SlackToken.objects.order_by("-created_at").first()
                        if token_obj:
                            headers = {
                                "Authorization": f"Bearer {token_obj.access_token}",
                                "Content-Type": "application/json",
                            }
                            feedback_blocks = [
                                {
                                    "type": "section",
                                    "text": {"type": "mrkdwn", "text": f"How helpful was the agent's response for Ticket #{ticket_id}?"}
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {"type": "plain_text", "text": "👍 Helpful"},
                                        "value": f"feedback_positive_{ticket_id}",
                                        "action_id": "feedback_positive"
                                    },
                                    {
                                        "type": "button",
                                        "text": {"type": "plain_text", "text": "👎 Not Helpful"},
                                        "value": f"feedback_negative_{ticket_id}",
                                        "action_id": "feedback_negative"
                                    }
                                ]
                            }
                        ]
                            requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                                "channel": user_id,
                                "blocks": feedback_blocks,
                                "text": "Please rate the agent's response."
                            })
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
                    token_obj = SlackToken.objects.order_by("-created_at").first()
                    if token_obj:
                        headers = {
                            "Authorization": f"Bearer {token_obj.access_token}",
                            "Content-Type": "application/json",
                        }
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
                        requests.post("https://slack.com/api/views.open", headers=headers, json=data)
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
                    token_obj = SlackToken.objects.order_by("-created_at").first()
                    if token_obj:
                        headers = {
                            "Authorization": f"Bearer {token_obj.access_token}",
                            "Content-Type": "application/json",
                        }
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
                        requests.post("https://slack.com/api/views.open", headers=headers, json=data)
                    return HttpResponse()
        # Handle view_submission (modal)
        elif payload_type == "view_submission":
            callback_id = payload.get("view", {}).get("callback_id")
            # --- Ticket creation modal ---
            if callback_id == "resolvemeq_modal":
                values = payload["view"]["state"]["values"]
                category = values["category_block"]["category"]["selected_option"]["value"]
                issue_type = values["issue_type_block"]["issue_type"]["selected_option"]["value"]
                urgency = values["urgency_block"]["urgency"]["selected_option"]["value"]
                description = values["description_block"]["description"]["value"]
                screenshot = values.get("screenshot_block", {}).get("screenshot", {}).get("value", "")
                user_id = payload["user"]["id"]
                from tickets.models import Ticket, TicketInteraction
                user, _ = User.objects.get_or_create(username=user_id, defaults={"email": f"{user_id}@slack.local"})
                ticket = Ticket.objects.create(
                    user=user,
                    issue_type=f"{issue_type} ({urgency})",
                    status="new",
                    description=description,
                    screenshot=screenshot,
                    category=category,
                )
                TicketInteraction.objects.create(
                    ticket=ticket,
                    user=user,
                    interaction_type="user_message",
                    content=f"Ticket created: {description}"
                )
                notify_user_ticket_created(user_id, ticket.ticket_id)
                return JsonResponse({"response_action": "clear"})
            # --- Clarification modal ---
            elif callback_id == "clarify_modal":
                ticket_id = payload["view"].get("private_metadata")
                values = payload["view"]["state"]["values"]
                description = values["description_block"]["description"]["value"]
                issue_type = values["issue_type_block"]["issue_type"]["value"]
                user_id = payload["user"]["id"]
                from tickets.models import Ticket, TicketInteraction
                try:
                    ticket = Ticket.objects.get(ticket_id=ticket_id)
                except Ticket.DoesNotExist:
                    # Notify user in Slack if ticket not found
                    token_obj = SlackToken.objects.order_by("-created_at").first()
                    if token_obj:
                        headers = {
                            "Authorization": f"Bearer {token_obj.access_token}",
                            "Content-Type": "application/json",
                        }
                        requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                            "channel": user_id,
                            "text": "Sorry, we couldn't find your ticket to clarify. Please try again or contact IT."
                        })
                    return JsonResponse({"response_action": "clear"})
                try:
                    ticket.description = description
                    ticket.issue_type = issue_type
                    ticket.save()
                    TicketInteraction.objects.create(
                        ticket=ticket,
                        user=ticket.user,
                        interaction_type="clarification",
                        content=f"User clarified: Description='{description}', Issue Type='{issue_type}'"
                    )
                    from tickets.tasks import process_ticket_with_agent
                    process_ticket_with_agent.delay(ticket.ticket_id)
                except Exception as e:
                    # Notify user in Slack if clarification fails
                    token_obj = SlackToken.objects.order_by("-created_at").first()
                    if token_obj:
                        headers = {
                            "Authorization": f"Bearer {token_obj.access_token}",
                            "Content-Type": "application/json",
                        }
                        requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                            "channel": user_id,
                            "text": f"Sorry, there was an error saving your clarification: {str(e)}"
                        })
                return JsonResponse({"response_action": "clear"})
            # --- Feedback text modal ---
            elif callback_id == "feedback_text_modal":
                ticket_id = payload["view"].get("private_metadata")
                feedback = payload["view"]["state"]["values"]["feedback_block"]["feedback_text"]["value"]
                user_id = payload["user"]["id"]
                from tickets.models import Ticket, TicketInteraction
                try:
                    ticket = Ticket.objects.get(ticket_id=ticket_id)
                    TicketInteraction.objects.create(
                        ticket=ticket,
                        user=ticket.user,
                        interaction_type="feedback",
                        content=f"User feedback: {feedback}"
                    )
                    # Send confirmation to user
                    token_obj = SlackToken.objects.order_by("-created_at").first()
                    if token_obj:
                        headers = {
                            "Authorization": f"Bearer {token_obj.access_token}",
                            "Content-Type": "application/json",
                        }
                        requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                            "channel": user_id,
                            "text": "Thank you for your feedback! Our IT team will review it shortly."
                        })
                    # (Optional) Notify IT staff (e.g., send to a channel)
                    # requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={
                    #     "channel": "#it-support",
                    #     "text": f"New feedback for Ticket #{ticket_id}: {feedback}"
                    # })
                except Exception:
                    pass
                return JsonResponse({"response_action": "clear"})
            # --- Add more modal types as needed ---
            return JsonResponse({}, status=200)
        # Always return 200 OK for unknown or unhandled payloads
        return HttpResponse(status=200)

def notify_user_agent_response(user_id, ticket_id, agent_response, thread_ts=None):
    """
    Sends the agent's analysis and recommendations to the user via Slack DM, with interactive buttons.
    Args:
        user_id (str): Slack user ID or UUID.
        ticket_id (int): Ticket ID.
        agent_response (dict): The response from the agent (should be a dict, not JSON string).
        thread_ts (str, optional): Slack thread timestamp to reply in thread.
    """
    from .models import SlackToken
    import requests
    import json
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if not token_obj:
        return
    headers = {
        "Authorization": f"Bearer {token_obj.access_token}",
        "Content-Type": "application/json",
    }
    # Format the agent response for Slack
    if isinstance(agent_response, str):
        try:
            agent_response = json.loads(agent_response)
        except Exception:
            agent_response = {"analysis": {}, "recommendations": {}}
    analysis = agent_response.get("analysis", {})
    recommendations = agent_response.get("recommendations", {})
    # Build Slack blocks
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"🤖 *Agent Analysis for Ticket #{ticket_id}*"}},
    ]
    if analysis:
        for k, v in analysis.items():
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{k.replace('_',' ').capitalize()}:* {v}"}})
    if recommendations:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Recommendations:*"}})
        for k, v in recommendations.items():
            if isinstance(v, list):
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{k.replace('_',' ').capitalize()}:*\n- " + "\n- ".join(v)}})
            else:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{k.replace('_',' ').capitalize()}:* {v}"}})
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
    # If user_id looks like a Slack email (Uxxxx@slack.local), extract the Slack ID
    slack_channel = user_id
    if isinstance(user_id, str) and user_id.endswith("@slack.local"):
        slack_channel = user_id.split("@", 1)[0]
    payload = {
        "channel": slack_channel,
        "blocks": blocks,
        "text": f"Agent response for Ticket #{ticket_id}",
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts
    resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    import logging
    logging.getLogger(__name__).info(f"Sent agent response to Slack: {resp.text}")

def notify_user_auto_resolution(user_id, ticket_id, params):
    """
    Notify user that their ticket was automatically resolved.
    """
    from .models import SlackToken
    import requests
    
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if not token_obj:
        return
        
    headers = {
        "Authorization": f"Bearer {token_obj.access_token}",
        "Content-Type": "application/json",
    }
    
    # Extract Slack user ID if needed
    slack_channel = user_id
    if isinstance(user_id, str) and user_id.endswith("@slack.local"):
        slack_channel = user_id.split("@", 1)[0]
    
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
    
    resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    logging.getLogger(__name__).info(f"Sent auto-resolution notification: {resp.text}")

def notify_escalation(user_id, ticket_id, params):
    """
    Notify user that their ticket has been escalated.
    """
    from .models import SlackToken
    import requests
    
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if not token_obj:
        return
        
    headers = {
        "Authorization": f"Bearer {token_obj.access_token}",
        "Content-Type": "application/json",
    }
    
    # Extract Slack user ID if needed
    slack_channel = user_id
    if isinstance(user_id, str) and user_id.endswith("@slack.local"):
        slack_channel = user_id.split("@", 1)[0]
    
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
    
    resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    logging.getLogger(__name__).info(f"Sent escalation notification: {resp.text}")

def request_clarification_from_user(user_id, ticket_id, params):
    """
    Request clarification from user via Slack.
    """
    from .models import SlackToken
    import requests
    
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if not token_obj:
        return
        
    headers = {
        "Authorization": f"Bearer {token_obj.access_token}",
        "Content-Type": "application/json",
    }
    
    # Extract Slack user ID if needed
    slack_channel = user_id
    if isinstance(user_id, str) and user_id.endswith("@slack.local"):
        slack_channel = user_id.split("@", 1)[0]
    
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
    
    resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    logging.getLogger(__name__).info(f"Sent clarification request: {resp.text}")

def send_solution_with_followup(user_id, ticket_id, params):
    """
    Send solution to user with automatic follow-up scheduled.
    """
    from .models import SlackToken
    import requests
    
    token_obj = SlackToken.objects.order_by("-created_at").first()
    if not token_obj:
        return
        
    headers = {
        "Authorization": f"Bearer {token_obj.access_token}",
        "Content-Type": "application/json",
    }
    
    # Extract Slack user ID if needed
    slack_channel = user_id
    if isinstance(user_id, str) and user_id.endswith("@slack.local"):
        slack_channel = user_id.split("@", 1)[0]
    
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
    
    resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    logging.getLogger(__name__).info(f"Sent solution with follow-up: {resp.text}")
