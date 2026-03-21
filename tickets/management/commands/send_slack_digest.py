from django.core.management.base import BaseCommand
from tickets.models import Ticket
from integrations.models import SlackToken
import requests

class Command(BaseCommand):
    help = "Send daily Slack digest of open tickets"

    def handle(self, *args, **kwargs):
        open_tickets = Ticket.objects.filter(
            status__in=["new", "open", "in_progress", "in-progress"]
        )
        if not open_tickets.exists():
            return

        digest = "*Daily Open Tickets Digest:*\n"
        for t in open_tickets:
            digest += f"- #{t.ticket_id}: {t.issue_type} (by {t.user.name if t.user else t.user_id})\n"

        token_obj = SlackToken.objects.order_by("-created_at").first()
        if token_obj:
            headers = {
                "Authorization": f"Bearer {token_obj.access_token}",
                "Content-Type": "application/json",
            }
            data = {
                "channel": "D08V7L2L631",  # Replace with your actual channel ID
                "text": digest,
            }
            resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=data)
            print("Slack digest response:", resp.text)
