from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.models import ActionHistory, Ticket
from tickets.predictive_routing import (
    get_routing_metrics,
    record_routing_reassignment,
    suggest_assignee,
)
from tickets.services import create_ticket_with_reporter

User = get_user_model()


@override_settings(
    PREDICTIVE_ROUTING_ENABLED=True,
    PREDICTIVE_ROUTING_AUTO_ASSIGN_MIN_CONFIDENCE=0.4,
    PREDICTIVE_ROUTING_LOOKBACK_DAYS=90,
)
class PredictiveRoutingTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", email="owner@example.com", password="x")
        self.agent_a = User.objects.create_user(username="agent_a", email="a@example.com", password="x")
        self.agent_b = User.objects.create_user(username="agent_b", email="b@example.com", password="x")
        self.reporter = User.objects.create_user(username="rep1", email="rep@example.com", password="x")
        self.team = Team.objects.create(name="IT", owner=self.owner, is_active=True)
        self.team.members.add(self.owner, self.agent_a, self.agent_b, self.reporter)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.reporter)
        prefs.active_team = self.team
        prefs.save()
        self.client = APIClient()
        self.client.force_authenticate(self.reporter)

    def _seed_history(self):
        for _ in range(3):
            Ticket.objects.create(
                user=self.reporter,
                team=self.team,
                issue_type="VPN",
                category="vpn",
                status="resolved",
                assigned_to=self.agent_a,
                description="done",
            )
        Ticket.objects.create(
            user=self.reporter,
            team=self.team,
            issue_type="WiFi",
            category="wifi",
            status="open",
            assigned_to=self.agent_b,
            description="open",
        )

    def test_suggest_assignee_prefers_category_expert(self):
        self._seed_history()
        ticket = Ticket.objects.create(
            user=self.reporter,
            team=self.team,
            issue_type="VPN issue",
            category="vpn",
            status="new",
            description="help",
        )
        suggestion = suggest_assignee(ticket)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["suggested_assignee_id"], str(self.agent_a.id))
        self.assertGreater(suggestion["confidence"], 0.3)

    def test_auto_assign_on_create(self):
        self._seed_history()
        ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN down",
            description="cannot connect",
            category="vpn",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to_id, self.agent_a.id)
        self.assertTrue(ActionHistory.objects.filter(ticket=ticket, action_type="PREDICTIVE_ROUTE").exists())

    def test_reassignment_metric_tracks_predictive_override(self):
        self._seed_history()
        ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN down",
            description="cannot connect",
            category="vpn",
        )
        ticket.refresh_from_db()
        previous = ticket.assigned_to_id
        record_routing_reassignment(ticket, previous, self.agent_b.id)
        metrics = get_routing_metrics()
        self.assertGreaterEqual(metrics["routing_reassigned"], 1)

    def test_get_ticket_includes_routing_suggestion(self):
        self._seed_history()
        ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN down",
            description="cannot connect",
            category="vpn",
        )
        resp = self.client.get(f"/api/tickets/{ticket.ticket_id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("routing_suggestion", resp.data)

    def test_routing_metrics_endpoint(self):
        resp = self.client.get("/api/tickets/routing/metrics/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("routing_applied", resp.data)
