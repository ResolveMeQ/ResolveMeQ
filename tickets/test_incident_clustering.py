from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from base.models import Team
from tickets.incident_clustering import find_or_join_incident
from tickets.models import Incident, Ticket, TicketInteraction
from tickets.services import create_ticket_with_reporter

User = get_user_model()


@override_settings(INCIDENT_CLUSTER_WINDOW_MINUTES=60, INCIDENT_CLUSTER_MIN_SIZE=3, INCIDENT_CLUSTER_SIMILARITY_THRESHOLD=0.6)
class IncidentClusteringTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", email="owner1@example.com", password="x")
        self.reporter_a = User.objects.create_user(username="repA", email="repA@example.com", password="x")
        self.reporter_b = User.objects.create_user(username="repB", email="repB@example.com", password="x")
        self.reporter_c = User.objects.create_user(username="repC", email="repC@example.com", password="x")
        self.reporter_d = User.objects.create_user(username="repD", email="repD@example.com", password="x")
        self.team = Team.objects.create(name="Cluster Co", owner=self.owner)
        self.other_team = Team.objects.create(name="Other Co", owner=self.owner)

    _UNSET = object()

    def _make_ticket(self, reporter, team=_UNSET, **overrides):
        defaults = dict(
            user=reporter,
            team=self.team if team is self._UNSET else team,
            issue_type="VPN down",
            category="vpn",
            status="new",
            description="I cannot connect to the VPN from home",
        )
        defaults.update(overrides)
        return Ticket.objects.create(**defaults)

    def test_creates_incident_once_min_size_reached(self):
        self._make_ticket(self.reporter_a)
        self._make_ticket(self.reporter_b)
        third = self._make_ticket(self.reporter_c)

        incident = find_or_join_incident(third)

        self.assertIsNotNone(incident)
        self.assertEqual(incident.tickets.count(), 3)
        self.assertTrue(
            TicketInteraction.objects.filter(ticket=third, content__icontains="Incident").exists()
        )

    def test_below_min_size_does_not_create_incident(self):
        self._make_ticket(self.reporter_a)
        second = self._make_ticket(self.reporter_b)

        incident = find_or_join_incident(second)

        self.assertIsNone(incident)
        self.assertEqual(Incident.objects.count(), 0)

    def test_fourth_similar_ticket_joins_existing_incident(self):
        self._make_ticket(self.reporter_a)
        self._make_ticket(self.reporter_b)
        third = self._make_ticket(self.reporter_c)
        find_or_join_incident(third)
        self.assertEqual(Incident.objects.count(), 1)

        fourth = self._make_ticket(self.reporter_d)
        incident = find_or_join_incident(fourth)

        self.assertEqual(Incident.objects.count(), 1)  # joined, not a new one
        fourth.refresh_from_db()
        self.assertEqual(fourth.incident_id, incident.pk)
        self.assertEqual(incident.tickets.count(), 4)

    def test_does_not_cluster_same_reporter(self):
        # Same reporter filing repeatedly is duplicate detection's job, not incident clustering.
        self._make_ticket(self.reporter_a)
        self._make_ticket(self.reporter_a)
        third = self._make_ticket(self.reporter_a)

        incident = find_or_join_incident(third)

        self.assertIsNone(incident)

    def test_does_not_cluster_across_teams(self):
        self._make_ticket(self.reporter_a, team=self.other_team)
        self._make_ticket(self.reporter_b, team=self.other_team)
        third = self._make_ticket(self.reporter_c)  # different team

        incident = find_or_join_incident(third)

        self.assertIsNone(incident)

    def test_does_not_cluster_across_categories(self):
        self._make_ticket(self.reporter_a, category="wifi", issue_type="WiFi down", description="wifi is dead")
        self._make_ticket(self.reporter_b, category="wifi", issue_type="WiFi down", description="wifi is dead")
        third = self._make_ticket(self.reporter_c)  # vpn category

        incident = find_or_join_incident(third)

        self.assertIsNone(incident)

    def test_no_team_ticket_is_skipped(self):
        self._make_ticket(self.reporter_a, team=None)
        self._make_ticket(self.reporter_b, team=None)
        third = self._make_ticket(self.reporter_c, team=None)

        incident = find_or_join_incident(third)

        self.assertIsNone(incident)

    def test_dissimilar_tickets_in_same_category_do_not_cluster(self):
        self._make_ticket(self.reporter_a, issue_type="Printer jam", description="paper stuck in tray")
        self._make_ticket(self.reporter_b, issue_type="Slow VPN speeds", description="throughput is low")
        third = self._make_ticket(self.reporter_c, issue_type="VPN certificate expired", description="cert error on login")

        incident = find_or_join_incident(third)

        self.assertIsNone(incident)

    def test_clustering_failure_does_not_break_ticket_creation(self):
        from unittest.mock import patch

        self._make_ticket(self.reporter_a)
        self._make_ticket(self.reporter_b)
        with patch("tickets.incident_clustering.find_or_join_incident", side_effect=RuntimeError("boom")):
            ticket = create_ticket_with_reporter(
                self.reporter_c,
                self.team,
                issue_type="VPN down",
                description="I cannot connect to the VPN from home",
                category="vpn",
            )
        self.assertIsNotNone(ticket.pk)

    def test_serializer_exposes_incident_and_siblings(self):
        from tickets.serializers import TicketSerializer

        self._make_ticket(self.reporter_a)
        self._make_ticket(self.reporter_b)
        third = self._make_ticket(self.reporter_c)
        incident = find_or_join_incident(third)
        third.refresh_from_db()

        data = TicketSerializer(third).data
        self.assertEqual(data["incident"], incident.pk)
        self.assertEqual(len(data["incident_tickets"]), 2)
