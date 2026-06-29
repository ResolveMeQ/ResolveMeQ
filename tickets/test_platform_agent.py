"""
Tests for ResolveMeQ platform support staff (User.is_platform_agent) claiming/replying to
escalated tickets across customer teams they don't belong to, alongside the existing
self-serve (same-team) claim model.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .chat_models import ChatMessage, Conversation  # noqa: F401 -- import side effect: registers
# Conversation/ChatMessage (defined outside models.py) with the app registry so isolated runs of
# *this* test module create their tables too; without it, only test runs that happen to also
# discover a chat_*-importing module would (e.g. tickets.test_chat_agent_reply).
from .models import Ticket
from .scoping import tickets_queryset_for_user, user_can_access_ticket, user_can_assign_agent

User = get_user_model()


class PlatformAgentAccessTest(TestCase):
    def setUp(self):
        from base.models import Team, UserPreferences

        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="customerX", email="customerX@example.com", password="testpass123"
        )
        self.other_team_member = User.objects.create_user(
            username="teammateX", email="teammateX@example.com", password="testpass123"
        )
        self.platform_agent = User.objects.create_user(
            username="platform1", email="platform1@example.com", password="testpass123",
            is_platform_agent=True,
        )
        self.team = Team.objects.create(name="Customer Co", owner=self.customer)
        self.team.members.add(self.other_team_member)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.other_team_member)
        prefs.active_team = self.team
        prefs.save()

        self.escalated_ticket = Ticket.objects.create(
            user=self.customer, team=self.team, issue_type="server (critical)", status="escalated",
            description="Server down", category="server",
        )
        self.escalated_ticket.escalated_at = timezone.now()
        self.escalated_ticket.save()

        self.untouched_ticket = Ticket.objects.create(
            user=self.customer, team=self.team, issue_type="printer", status="new",
            description="Printer jam", category="printer",
        )

    def test_platform_agent_can_access_escalated_ticket_outside_their_team(self):
        self.assertTrue(user_can_access_ticket(self.platform_agent, self.escalated_ticket))

    def test_platform_agent_cannot_access_untouched_ticket(self):
        """Boundary: not blanket account access -- only escalated/claimed tickets."""
        self.assertFalse(user_can_access_ticket(self.platform_agent, self.untouched_ticket))

    def test_platform_agent_keeps_access_after_claiming_even_if_resolved(self):
        self.escalated_ticket.claimed_at = timezone.now()
        self.escalated_ticket.assigned_to = self.platform_agent
        self.escalated_ticket.status = "resolved"
        self.escalated_ticket.save()
        self.assertTrue(user_can_access_ticket(self.platform_agent, self.escalated_ticket))

    def test_regular_team_member_access_unchanged(self):
        self.assertTrue(user_can_access_ticket(self.other_team_member, self.escalated_ticket))
        self.assertTrue(user_can_access_ticket(self.other_team_member, self.untouched_ticket))
        outsider = User.objects.create_user(username="outsiderX", email="outsiderX@example.com", password="testpass123")
        self.assertFalse(user_can_access_ticket(outsider, self.escalated_ticket))

    def test_user_can_assign_agent_true_for_platform_agent_regardless_of_team(self):
        self.assertTrue(user_can_assign_agent(self.escalated_ticket, self.platform_agent))

    def test_queryset_for_platform_agent_includes_cross_team_escalated_tickets(self):
        qs = tickets_queryset_for_user(self.platform_agent)
        self.assertIn(self.escalated_ticket, qs)
        self.assertNotIn(self.untouched_ticket, qs)

    def test_queryset_for_regular_user_excludes_other_teams(self):
        from base.models import Team, UserPreferences

        unrelated_user = User.objects.create_user(
            username="unrelatedX", email="unrelatedX@example.com", password="testpass123"
        )
        other_team = Team.objects.create(name="Other Co", owner=unrelated_user)
        prefs, _ = UserPreferences.objects.get_or_create(user=unrelated_user)
        prefs.active_team = other_team
        prefs.save()

        qs = tickets_queryset_for_user(unrelated_user)
        self.assertNotIn(self.escalated_ticket, qs)

    @patch("tickets.views.dispatch_ticket_claimed_email")
    def test_platform_agent_can_claim_via_assign_endpoint(self, mock_email):
        self.client.force_authenticate(user=self.platform_agent)
        resp = self.client.post(
            f"/api/tickets/{self.escalated_ticket.ticket_id}/assign/",
            {"agent_id": str(self.platform_agent.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.escalated_ticket.refresh_from_db()
        self.assertEqual(self.escalated_ticket.assigned_to_id, self.platform_agent.id)
        self.assertIsNotNone(self.escalated_ticket.claimed_at)

    @patch("tickets.chat_views.dispatch_ticket_comment_email")
    def test_platform_agent_can_reply_after_claiming(self, mock_email):
        self.escalated_ticket.claimed_at = timezone.now()
        self.escalated_ticket.assigned_to = self.platform_agent
        self.escalated_ticket.save()
        self.client.force_authenticate(user=self.platform_agent)

        resp = self.client.post(
            f"/api/tickets/{self.escalated_ticket.ticket_id}/chat/agent-reply/",
            {"message": "This is ResolveMeQ support, looking into your server now."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_escalation_queue_shows_cross_team_tickets_for_platform_agent(self):
        self.client.force_authenticate(user=self.platform_agent)
        resp = self.client.get("/api/tickets/escalated/")
        ids = [t["ticket_id"] for t in resp.data["tickets"]]
        self.assertIn(self.escalated_ticket.ticket_id, ids)
        self.assertEqual(resp.data["tickets"][0]["team_name"], "Customer Co")
