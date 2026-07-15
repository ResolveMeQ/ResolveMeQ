from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team
from tickets.models import Ticket

User = get_user_model()


class BulkUpdateTicketsTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="bulk1", email="bulk1@example.com", password="pw")
        self.other_user = User.objects.create_user(username="bulk2", email="bulk2@example.com", password="pw")
        self.team = Team.objects.create(name="Bulk Co", owner=self.owner)
        self.team.members.add(self.owner)

        self.t1 = Ticket.objects.create(user=self.owner, team=self.team, issue_type="A", category="other", status="new")
        self.t2 = Ticket.objects.create(user=self.owner, team=self.team, issue_type="B", category="other", status="open")
        self.t3 = Ticket.objects.create(user=self.other_user, issue_type="C", category="other", status="new")

        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = "/api/tickets/bulk-update/"

    def test_requires_ticket_ids_and_status(self):
        resp = self.client.post(self.url, {"ticket_ids": [self.t1.ticket_id]}, format="json")
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(self.url, {"status": "resolved"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_rejects_invalid_status(self):
        resp = self.client.post(
            self.url, {"ticket_ids": [self.t1.ticket_id], "status": "not_a_real_status"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.status, "new")

    def test_updates_only_own_visible_tickets(self):
        resp = self.client.post(
            self.url,
            {"ticket_ids": [self.t1.ticket_id, self.t2.ticket_id, self.t3.ticket_id], "status": "resolved"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated"], 2)
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.t3.refresh_from_db()
        self.assertEqual(self.t1.status, "resolved")
        self.assertEqual(self.t2.status, "resolved")
        self.assertEqual(self.t3.status, "new")  # not visible to this user, untouched

    def test_no_matching_tickets_reports_zero(self):
        resp = self.client.post(self.url, {"ticket_ids": [self.t3.ticket_id], "status": "resolved"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated"], 0)
