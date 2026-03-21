from django.core.management.base import BaseCommand
from django.utils import timezone
from tickets.models import Ticket
from integrations.models import SlackToken
import requests

class Command(BaseCommand):
    help = "Escalate urgent tickets not updated in 2 hours"

    def handle(self, *args, **kwargs):
        two_hours_ago = timezone.now() - timezone.timedelta(hours=2)
        # Find urgent tickets not resolved and not updated in 2 hours
        urgent_tickets = Ticket.objects.filter(
            status__in=["new", "open", "in_progress", "in-progress"],
            issue_type__icontains="urgent",
            updated_at__lt=two_hours_ago
        )
        if not urgent_tickets.exists():
            return

        message = "*Escalation Alert: Urgent tickets need attention!*\n"
        for t in urgent_tickets:
            message += f"- #{t.ticket_id}: {t.issue_type} (by {t.user.name if t.user else t.user_id})\n"

        token_obj = SlackToken.objects.order_by("-created_at").first()
        if token_obj:
            headers = {
                "Authorization": f"Bearer {token_obj.access_token}",
                "Content-Type": "application/json",
            }
            data = {
                "channel": "C12345678",  # Replace with your IT team's channel ID
                "text": message,
            }
            resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=data)
            print("Slack escalation response:", resp.text)
