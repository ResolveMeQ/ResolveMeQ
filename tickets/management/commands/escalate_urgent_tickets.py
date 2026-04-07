from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from tickets.models import Ticket
from integrations.models import SlackToken
from integrations import slack_installation as slack_inst


class Command(BaseCommand):
    help = "Escalate urgent tickets not updated in 2 hours (posts to SLACK_ESCALATION_ALERT_CHANNEL or SLACK_ESCALATION_CHANNEL)"

    def handle(self, *args, **kwargs):
        channel = (
            getattr(settings, "SLACK_ESCALATION_ALERT_CHANNEL", "").strip()
            or getattr(settings, "SLACK_ESCALATION_CHANNEL", "").strip()
        )
        if not channel:
            self.stdout.write("No Slack alert channel configured; skipping.")
            return

        two_hours_ago = timezone.now() - timezone.timedelta(hours=2)
        urgent_tickets = Ticket.objects.filter(
            status__in=["new", "open", "in_progress", "in-progress"],
            issue_type__icontains="urgent",
            updated_at__lt=two_hours_ago,
        )
        if not urgent_tickets.exists():
            return

        message = "*Escalation Alert: Urgent tickets need attention!*\n"
        for t in urgent_tickets:
            uname = getattr(t.user, "get_full_name", lambda: "")() or (
                t.user.username if t.user else "unknown"
            )
            message += f"- #{t.ticket_id}: {t.issue_type} (by {uname})\n"

        for inst in SlackToken.objects.filter(is_active=True):
            slack_inst.slack_api_post(
                inst,
                "chat.postMessage",
                {"channel": channel, "text": message},
            )
