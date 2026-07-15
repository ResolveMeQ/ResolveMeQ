from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from base.models import Team
from tickets.models import Ticket, TicketInteraction
from tickets.services import create_ticket_with_reporter
from tickets.similarity import find_and_flag_duplicate, score_similarity

User = get_user_model()


class ScoreSimilarityTest(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(username="rep1", email="rep@example.com", password="x")

    def test_identical_category_issue_type_and_description_scores_high(self):
        a = Ticket.objects.create(
            user=self.reporter,
            issue_type="VPN not connecting",
            category="vpn",
            status="new",
            description="I cannot connect to the VPN from home",
        )
        b = Ticket.objects.create(
            user=self.reporter,
            issue_type="VPN not connecting",
            category="vpn",
            status="open",
            description="I cannot connect to the VPN from home",
        )
        self.assertGreaterEqual(score_similarity(a, b), 0.7)

    def test_different_category_scores_lower(self):
        a = Ticket.objects.create(
            user=self.reporter, issue_type="VPN down", category="vpn", status="new", description="cannot connect"
        )
        b = Ticket.objects.create(
            user=self.reporter, issue_type="VPN down", category="wifi", status="open", description="cannot connect"
        )
        self.assertLess(score_similarity(a, b), score_similarity(a, a))

    def test_no_overlap_scores_zero(self):
        a = Ticket.objects.create(
            user=self.reporter, issue_type="VPN down", category="vpn", status="new", description="cannot connect"
        )
        b = Ticket.objects.create(
            user=self.reporter, issue_type="Printer jam", category="hardware", status="open", description="paper stuck"
        )
        self.assertEqual(score_similarity(a, b), 0.0)


@override_settings(DUPLICATE_TICKET_SIMILARITY_THRESHOLD=0.7)
class FindAndFlagDuplicateTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", email="owner@example.com", password="x")
        self.reporter = User.objects.create_user(username="rep1", email="rep@example.com", password="x")
        self.other_reporter = User.objects.create_user(username="rep2", email="rep2@example.com", password="x")
        self.team = Team.objects.create(name="IT", owner=self.owner, is_active=True)

    def _existing(self, **overrides):
        defaults = dict(
            user=self.reporter,
            team=self.team,
            issue_type="VPN not connecting",
            category="vpn",
            status="open",
            description="I cannot connect to the VPN from home",
        )
        defaults.update(overrides)
        return Ticket.objects.create(**defaults)

    def test_flags_high_overlap_ticket_from_same_reporter(self):
        existing = self._existing()
        new_ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN not connecting",
            description="I cannot connect to the VPN from home",
            category="vpn",
        )
        new_ticket.refresh_from_db()
        self.assertEqual(new_ticket.duplicate_of_id, existing.ticket_id)
        self.assertTrue(
            TicketInteraction.objects.filter(ticket=new_ticket, content__icontains="Possible duplicate").exists()
        )

    def test_does_not_flag_different_reporter(self):
        self._existing(user=self.other_reporter)
        new_ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN not connecting",
            description="I cannot connect to the VPN from home",
            category="vpn",
        )
        new_ticket.refresh_from_db()
        self.assertIsNone(new_ticket.duplicate_of_id)

    def test_does_not_flag_resolved_ticket(self):
        self._existing(status="resolved")
        new_ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN not connecting",
            description="I cannot connect to the VPN from home",
            category="vpn",
        )
        new_ticket.refresh_from_db()
        self.assertIsNone(new_ticket.duplicate_of_id)

    def test_does_not_flag_different_category(self):
        self._existing(category="wifi")
        new_ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN not connecting",
            description="I cannot connect to the VPN from home",
            category="vpn",
        )
        new_ticket.refresh_from_db()
        self.assertIsNone(new_ticket.duplicate_of_id)

    def test_below_threshold_is_not_flagged(self):
        self._existing(issue_type="Printer jam", description="paper stuck in tray 2")
        new_ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN not connecting",
            description="I cannot connect to the VPN from home",
            category="vpn",
        )
        new_ticket.refresh_from_db()
        self.assertIsNone(new_ticket.duplicate_of_id)

    def test_duplicate_check_failure_does_not_break_ticket_creation(self):
        self._existing()
        with patch("tickets.similarity.find_and_flag_duplicate", side_effect=RuntimeError("boom")):
            new_ticket = create_ticket_with_reporter(
                self.reporter,
                self.team,
                issue_type="VPN not connecting",
                description="I cannot connect to the VPN from home",
                category="vpn",
            )
        self.assertIsNotNone(new_ticket.pk)

    def test_serializer_exposes_duplicate_of_and_duplicates(self):
        from tickets.serializers import TicketSerializer

        existing = self._existing()
        new_ticket = create_ticket_with_reporter(
            self.reporter,
            self.team,
            issue_type="VPN not connecting",
            description="I cannot connect to the VPN from home",
            category="vpn",
        )
        new_ticket.refresh_from_db()
        existing.refresh_from_db()

        new_data = TicketSerializer(new_ticket).data
        existing_data = TicketSerializer(existing).data

        self.assertEqual(new_data["duplicate_of"], existing.ticket_id)
        self.assertIn(new_ticket.ticket_id, existing_data["duplicates"])
