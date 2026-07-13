"""Tests for ticket agent payload helper."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from base.models import Team
from tickets.agent_payload import build_ticket_agent_payload
from tickets.models import Ticket

User = get_user_model()


class TicketAgentPayloadTest(TestCase):
    def test_includes_team_id_when_ticket_has_team(self):
        user = User.objects.create_user(username="u1", email="u1@example.com", password="pw")
        team = Team.objects.create(name="Payload Co", owner=user)
        ticket = Ticket.objects.create(
            user=user,
            team=team,
            issue_type="VPN issue",
            description="Cannot connect",
            category="network",
            status="new",
        )
        payload = build_ticket_agent_payload(ticket)
        self.assertEqual(payload["team_id"], str(team.id))
        self.assertEqual(payload["ticket_id"], ticket.ticket_id)
