from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.agent_usage import AgentQuotaResult
from tickets.chat_models import Conversation
from tickets.models import Ticket, TicketInteraction

User = get_user_model()

SAMPLE_AGENT_JSON_WITH_SCRIPT = {
    "confidence": 0.88,
    "recommended_action": "auto_resolve",
    "reasoning": "Restarting the print spooler clears the stuck queue.",
    "response_style": "guided_steps",
    "solution": {
        "steps": ["Open Services", "Restart the Print Spooler service"],
        "estimated_time": "2 minutes",
        "success_probability": 0.9,
        "immediate_actions": [],
        "preventive_measures": [],
        "remediation_script": {
            "platform": "windows",
            "shell": "powershell",
            "script": "Restart-Service -Name Spooler -Force",
            "summary": "Restarts the print spooler service.",
        },
    },
    "analysis": {"category": "printer_issue", "severity": "low", "complexity": "low"},
}

SAMPLE_AGENT_JSON_NO_SCRIPT = {
    **SAMPLE_AGENT_JSON_WITH_SCRIPT,
    "solution": {**SAMPLE_AGENT_JSON_WITH_SCRIPT["solution"], "remediation_script": None},
}


class ReportedPlatformFieldTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="platformuser", email="platform@example.com", password="pw"
        )

    def test_ticket_stores_reported_platform(self):
        ticket = Ticket.objects.create(
            user=self.user,
            issue_type="Printer stuck",
            description="Print jobs are stuck in the queue",
            category="printer",
            status="new",
            reported_platform="windows",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.reported_platform, "windows")

    def test_reported_platform_defaults_to_none(self):
        ticket = Ticket.objects.create(
            user=self.user,
            issue_type="Printer stuck",
            category="printer",
            status="new",
        )
        self.assertIsNone(ticket.reported_platform)


class RemediationScriptChatFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="scriptuser", email="script@example.com", password="pw"
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type="Printer stuck (high)",
            description="Print jobs are stuck in the queue",
            category="printer",
            status="in_progress",
            reported_platform="windows",
        )
        Conversation.objects.create(ticket=self.ticket, user=self.user, summary="")

    @patch("tickets.chat_views.requests.post")
    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_remediation_script_flows_into_chat_message_metadata(self, mock_quota, mock_post):
        mock_quota.return_value = AgentQuotaResult(allowed=True, used=1, limit=100)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = SAMPLE_AGENT_JSON_WITH_SCRIPT
        mock_post.return_value = mock_resp

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/",
            {"message": "my printer is jammed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp.content))

        ai_message = resp.data["ai_message"]
        self.assertEqual(
            ai_message["metadata"]["remediation_script"]["script"],
            "Restart-Service -Name Spooler -Force",
        )
        self.assertEqual(ai_message["metadata"]["remediation_script"]["platform"], "windows")

        # The analyze payload sent to the agent should carry the reporter's known platform.
        sent_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_payload.get("reported_platform"), "windows")

    @patch("tickets.chat_views.requests.post")
    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_remediation_script_shown_logs_ticket_interaction(self, mock_quota, mock_post):
        mock_quota.return_value = AgentQuotaResult(allowed=True, used=1, limit=100)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = SAMPLE_AGENT_JSON_WITH_SCRIPT
        mock_post.return_value = mock_resp

        client = APIClient()
        client.force_authenticate(self.user)
        client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/",
            {"message": "my printer is jammed"},
            format="json",
        )

        logged = TicketInteraction.objects.filter(
            ticket=self.ticket, content__icontains="Remediation script shown"
        )
        self.assertTrue(logged.exists())

    @patch("tickets.chat_views.requests.post")
    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_no_script_no_interaction_logged(self, mock_quota, mock_post):
        mock_quota.return_value = AgentQuotaResult(allowed=True, used=1, limit=100)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = SAMPLE_AGENT_JSON_NO_SCRIPT
        mock_post.return_value = mock_resp

        client = APIClient()
        client.force_authenticate(self.user)
        client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/",
            {"message": "my printer is jammed"},
            format="json",
        )

        logged = TicketInteraction.objects.filter(
            ticket=self.ticket, content__icontains="Remediation script shown"
        )
        self.assertFalse(logged.exists())
