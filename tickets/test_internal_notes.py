"""
Internal notes (add_comment) must never reach the ticket reporter -- that's what
send_agent_reply ("Reply to customer") is for. Regression guard for a bug where
staff-authored comments were silently emailed/notified/messaged to the customer
despite the UI explicitly labeling the section "not sent to the customer".
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import InAppNotification, Team, UserPreferences
from .models import Ticket

User = get_user_model()


class InternalNoteDoesNotReachCustomerTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.requester = User.objects.create_user(
            username="reporter1", email="reporter1@example.com", password="testpass123"
        )
        self.agent = User.objects.create_user(
            username="agent2", email="agent2@example.com", password="testpass123"
        )
        self.team = Team.objects.create(name="Support Team B", owner=self.requester)
        self.team.members.add(self.agent)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.agent)
        prefs.active_team = self.team
        prefs.save()

        self.ticket = Ticket.objects.create(
            user=self.requester, team=self.team, issue_type="printer (medium)",
            status="escalated", description="Printer offline", category="printer",
            assigned_to=self.agent, claimed_at=None,
        )

    @patch("tickets.views.dispatch_ticket_comment_email")
    @patch("integrations.notify.notify_ticket_reporter_message")
    def test_staff_comment_does_not_notify_or_email_the_requester(self, mock_reporter_notify, mock_email):
        self.client.force_authenticate(user=self.agent)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/comment/",
            {"comment": "Customer seems confused, let's double check the model number before replying."},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        mock_reporter_notify.assert_not_called()
        self.assertFalse(InAppNotification.objects.filter(user=self.requester).exists())
        if mock_email.called:
            recipients = list(mock_email.call_args.args[1])
            self.assertNotIn(self.requester, recipients)

    @patch("tickets.views.dispatch_ticket_comment_email")
    @patch("integrations.notify.notify_ticket_reporter_message")
    def test_staff_comment_notifies_other_staff_instead(self, mock_reporter_notify, mock_email):
        owner_prefs, _ = UserPreferences.objects.get_or_create(user=self.requester)
        another_agent = User.objects.create_user(
            username="agent3", email="agent3@example.com", password="testpass123"
        )
        self.team.members.add(another_agent)
        self.ticket.assigned_to = another_agent
        self.ticket.save(update_fields=["assigned_to"])

        self.client.force_authenticate(user=self.agent)
        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/comment/",
            {"comment": "Heads up, I've started looking into this."},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            InAppNotification.objects.filter(user=another_agent).exists()
        )
        self.assertFalse(InAppNotification.objects.filter(user=self.requester).exists())

    @patch("tickets.views.dispatch_ticket_comment_email")
    @patch("integrations.notify.notify_ticket_reporter_message")
    def test_requester_comment_still_notifies_assigned_agent(self, mock_reporter_notify, mock_email):
        self.client.force_authenticate(user=self.requester)
        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/comment/",
            {"comment": "Any update on this?"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(InAppNotification.objects.filter(user=self.agent).exists())
        mock_reporter_notify.assert_not_called()
