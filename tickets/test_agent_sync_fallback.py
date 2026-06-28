"""
Tests for the no-Celery-required agent processing path (tickets.tasks.process_ticket_with_agent_sync),
added so ticket creation degrades the same way the manual "process with agent" trigger always did
when Celery/the broker is unavailable, instead of the ticket silently never being analyzed.
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .autonomous_agent import AgentAction
from .models import ActionHistory, Ticket, TicketResolution
from .tasks import process_ticket_with_agent_sync

User = get_user_model()


def _quota_result(allowed=True):
    result = MagicMock()
    result.allowed = allowed
    return result


class ProcessTicketWithAgentSyncTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="syncuser", email="sync@example.com", password="testpass123"
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type="wifi (high)",
            status="new",
            description="Cannot connect to Wi-Fi",
            category="wifi",
        )

    @patch("tickets.tasks.execute_autonomous_action")
    @patch("tickets.tasks.try_consume_agent_operation", return_value=_quota_result(True))
    @patch("tickets.tasks.requests.post")
    def test_happy_path_saves_response_and_runs_autonomous_action(
        self, mock_post, mock_quota, mock_execute
    ):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "confidence": 0.9,
                "recommended_action": "auto_resolve",
                "analysis": {"category": "network_issue", "severity": "low", "complexity": "low"},
                "solution": {"steps": ["Restart router"], "estimated_time": "5m", "success_probability": 0.9},
                "reasoning": "Common Wi-Fi issue.",
                "assignment": {"team": "network-issue-support"},
            },
        )
        mock_post.return_value.raise_for_status = lambda: None

        ok = process_ticket_with_agent_sync(self.ticket, self.user)

        self.assertTrue(ok)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.agent_processed)
        self.assertEqual(self.ticket.agent_response["recommended_action"], "auto_resolve")
        mock_execute.assert_called_once()
        called_action = mock_execute.call_args[0][1]
        self.assertEqual(called_action, AgentAction.AUTO_RESOLVE.value)

    @patch("tickets.tasks.execute_autonomous_action")
    @patch("tickets.tasks.refund_agent_operation")
    @patch("tickets.tasks.try_consume_agent_operation", return_value=_quota_result(True))
    @patch("tickets.tasks.requests.post", side_effect=ConnectionError("agent unreachable"))
    def test_agent_unreachable_degrades_to_placeholder_and_refunds(
        self, mock_post, mock_quota, mock_refund, mock_execute
    ):
        ok = process_ticket_with_agent_sync(self.ticket, self.user)

        self.assertTrue(ok)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.agent_processed)
        self.assertEqual(self.ticket.agent_response["recommended_action"], "request_clarification")
        mock_refund.assert_called_once_with(self.user)

    @patch("tickets.tasks.try_consume_agent_operation", return_value=_quota_result(False))
    def test_quota_exceeded_does_not_process(self, mock_quota):
        ok = process_ticket_with_agent_sync(self.ticket, self.user)

        self.assertFalse(ok)
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.agent_processed)

    @patch("tickets.tasks.refund_agent_operation")
    def test_already_processed_refunds_when_precharged(self, mock_refund):
        self.ticket.agent_processed = True
        self.ticket.save()

        ok = process_ticket_with_agent_sync(self.ticket, self.user, billing_precharged=True)

        self.assertFalse(ok)
        mock_refund.assert_called_once_with(self.user)


class UpdateTicketStatusResolutionAuditTest(TestCase):
    """Manually-resolved tickets should get the same audit/rollback trail as autonomous auto_resolve."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="resolver", email="resolver@example.com", password="testpass123"
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type="wifi (high)",
            status="in_progress",
            description="Cannot connect to Wi-Fi",
            category="wifi",
        )

    def test_marking_resolved_creates_resolution_and_rollback_capable_action_history(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)

        resp = client.post(f"/api/tickets/{self.ticket.ticket_id}/status/", {"status": "resolved"})

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(TicketResolution.objects.filter(ticket=self.ticket).exists())
        action = ActionHistory.objects.get(ticket=self.ticket, action_type="MANUAL_RESOLVE")
        self.assertTrue(action.rollback_possible)
        self.assertEqual(action.rollback_steps, {"handler": "rollback_auto_resolve"})
        self.assertEqual(action.before_state, {"status": "in_progress"})
