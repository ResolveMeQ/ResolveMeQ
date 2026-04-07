from django.core.management.base import BaseCommand
from django.conf import settings
from tickets.models import Ticket
from integrations.models import SlackToken
from integrations import slack_installation as slack_inst


class Command(BaseCommand):
    help = "Send daily Slack digest of open tickets (uses SLACK_DIGEST_CHANNEL + active Slack installs)"

    def handle(self, *args, **kwargs):
        channel = getattr(settings, "SLACK_DIGEST_CHANNEL", "").strip()
        if not channel:
            self.stdout.write("SLACK_DIGEST_CHANNEL not set; skipping.")
            return

        open_tickets = Ticket.objects.filter(
            status__in=["new", "open", "in_progress", "in-progress"]
        )
        if not open_tickets.exists():
            return

        digest = "*Daily Open Tickets Digest:*\n"
        for t in open_tickets:
            uname = getattr(t.user, "get_full_name", lambda: "")() or (
                t.user.username if t.user else "unknown"
            )
            digest += f"- #{t.ticket_id}: {t.issue_type} (by {uname})\n"

        for inst in SlackToken.objects.filter(is_active=True).select_related("resolvemeq_team"):
            slack_inst.slack_api_post(
                inst,
                "chat.postMessage",
                {"channel": channel, "text": digest},
            )
