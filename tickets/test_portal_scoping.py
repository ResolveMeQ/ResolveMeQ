"""Portal ticket scoping, team context, search shape, and secured create."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.models import Ticket

User = get_user_model()


class PortalTicketScopingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.a = User.objects.create_user(username="a", email="a@example.com", password="pass12345")
        self.b = User.objects.create_user(username="b", email="b@example.com", password="pass12345")
        self.ta = Ticket.objects.create(
            user=self.a,
            issue_type="My wifi",
            status="open",
            category="wifi",
            description="cannot connect",
        )
        self.tb = Ticket.objects.create(
            user=self.b,
            issue_type="Wifi fixed",
            status="resolved",
            category="wifi",
            description="reset router fixed wifi",
        )

    def test_list_only_own_without_team(self):
        self.client.force_authenticate(user=self.a)
        r = self.client.get("/api/tickets/list/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [row["ticket_id"] for row in r.data]
        self.assertIn(self.ta.ticket_id, ids)
        self.assertNotIn(self.tb.ticket_id, ids)

    def test_get_other_ticket_forbidden(self):
        self.client.force_authenticate(user=self.a)
        r = self.client.get(f"/api/tickets/{self.tb.ticket_id}/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_returns_my_and_community_keys(self):
        self.client.force_authenticate(user=self.a)
        r = self.client.get("/api/tickets/search/", {"q": "wifi"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("my_tickets", r.data)
        self.assertIn("community_resolved", r.data)
        mine_ids = [t["ticket_id"] for t in r.data["my_tickets"]]
        self.assertIn(self.ta.ticket_id, mine_ids)
        comm_ids = [h["ticket_id"] for h in r.data["community_resolved"]]
        self.assertIn(self.tb.ticket_id, comm_ids)

    def test_active_team_sees_peer_tickets(self):
        team = Team.objects.create(name="Crew", owner=self.a)
        team.members.add(self.a, self.b)
        UserPreferences.objects.update_or_create(user=self.a, defaults={"active_team": team})
        self.ta.team = team
        self.ta.save(update_fields=["team"])
        self.tb.team = team
        self.tb.save(update_fields=["team"])
        self.client.force_authenticate(user=self.a)
        r = self.client.get("/api/tickets/list/")
        ids = [row["ticket_id"] for row in r.data]
        self.assertIn(self.ta.ticket_id, ids)
        self.assertIn(self.tb.ticket_id, ids)

    @patch("tickets.tasks.process_ticket_with_agent.delay")
    def test_create_sets_team_from_preferences(self, _mock_delay):
        team = Team.objects.create(name="Crew2", owner=self.a)
        team.members.add(self.a)
        UserPreferences.objects.update_or_create(user=self.a, defaults={"active_team": team})
        self.client.force_authenticate(user=self.a)
        r = self.client.post(
            "/api/tickets/",
            {
                "issue_type": "vpn",
                "description": "vpn down",
                "status": "new",
                "category": "vpn",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(r.data.get("team")), str(team.id))

    def test_create_requires_authentication_or_agent(self):
        r = self.client.post(
            "/api/tickets/",
            {
                "user": str(self.a.pk),
                "issue_type": "x",
                "status": "new",
                "category": "other",
            },
            format="json",
        )
        # No credentials → 401; some setups return 403 — both reject anonymous create
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
