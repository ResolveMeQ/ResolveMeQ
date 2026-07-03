from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.agent_usage import AgentQuotaResult
from tickets.chat_models import Conversation
from tickets.chat_views import _sync_ticket_agent_response_from_chat
from tickets.models import Ticket

User = get_user_model()

SAMPLE_AGENT_JSON = {
    "confidence": 0.91,
    "recommended_action": "auto_resolve",
    "reasoning": "Run the memory diagnostic tool and review results.",
    "response_style": "guided_steps",
    "solution": {
        "steps": ["Run memory diagnostic", "Reseat RAM if errors found"],
        "estimated_time": "15 minutes",
        "success_probability": 0.85,
        "immediate_actions": [],
        "preventive_measures": [],
    },
    "analysis": {"category": "hardware_failure", "severity": "high", "complexity": "medium"},
}


class SyncTicketAgentFromChatTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="syncuser", email="sync@example.com", password="pw"
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type="blue screen (high)",
            description="BSOD on boot",
            category="software",
            status="in_progress",
        )
        Conversation.objects.create(ticket=self.ticket, user=self.user, summary="")

    def test_sync_sets_agent_processed(self):
        _sync_ticket_agent_response_from_chat(self.ticket, SAMPLE_AGENT_JSON)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.agent_processed)
        self.assertEqual(self.ticket.agent_response.get("confidence"), 0.91)

    @patch("tickets.chat_views.requests.post")
    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_first_chat_message_updates_ticket_agent_response(self, mock_quota, mock_post):
        mock_quota.return_value = AgentQuotaResult(allowed=True, used=1, limit=100)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = SAMPLE_AGENT_JSON
        mock_post.return_value = mock_resp

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/",
            {"message": "what should I try first?"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp.content))
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.agent_processed)
        self.assertEqual(self.ticket.agent_response.get("confidence"), 0.91)
