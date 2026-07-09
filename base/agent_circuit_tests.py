from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base.agent_circuit import (
    agent_circuit_is_open,
    get_agent_slo_status,
    record_agent_failure,
    reset_agent_circuit_for_tests,
)
from base.agent_client import AgentCallError, agent_http_timeout, try_call_agent_analyze
from tickets.models import Ticket
from tickets.tasks import process_ticket_with_agent_sync

User = get_user_model()


def _quota_result(allowed=True):
    result = MagicMock()
    result.allowed = allowed
    return result


@override_settings(
    AI_AGENT_CIRCUIT_MAX_FAILURES=3,
    AI_AGENT_CIRCUIT_OPEN_SECONDS=120,
    AI_AGENT_HTTP_TIMEOUT=30,
    AI_AGENT_HTTP_TIMEOUT_MAX=30,
)
class AgentCircuitBreakerTest(TestCase):
    def setUp(self):
        reset_agent_circuit_for_tests()
        self.user = User.objects.create_user(
            username="circuituser",
            email="circuit@example.com",
            password="testpass123",
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type="vpn (high)",
            status="new",
            description="VPN down",
            category="vpn",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def tearDown(self):
        reset_agent_circuit_for_tests()

    def test_http_timeout_capped_at_30_seconds(self):
        self.assertEqual(agent_http_timeout(60), 30)
        self.assertEqual(agent_http_timeout(10), 10)

    @patch("base.agent_client.requests.post")
    def test_circuit_opens_after_repeated_failures(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("agent down")
        for _ in range(3):
            response, error = try_call_agent_analyze(
                {"ticket_id": 1}, ticket=self.ticket, timeout=5
            )
            self.assertIsNotNone(response)
            self.assertIsNotNone(error)
        self.assertTrue(agent_circuit_is_open())

    @patch("base.agent_client.requests.post")
    def test_circuit_open_skips_http_call(self, mock_post):
        for _ in range(3):
            record_agent_failure(10.0, "down")
        agent_response, err = try_call_agent_analyze(
            {"ticket_id": self.ticket.ticket_id},
            ticket=self.ticket,
            timeout=5,
        )
        self.assertTrue(agent_circuit_is_open())
        mock_post.assert_not_called()
        self.assertTrue(agent_response.get("agent_fallback"))
        self.assertIn("circuit", (err or "").lower())

    @patch("tickets.tasks.execute_autonomous_action")
    @patch("tickets.tasks.try_consume_agent_operation", return_value=_quota_result(True))
    @patch("base.agent_client.requests.post", side_effect=requests.ConnectionError("down"))
    def test_sync_ticket_processing_uses_fallback_without_hanging(
        self, mock_post, mock_quota, mock_execute
    ):
        ok = process_ticket_with_agent_sync(self.ticket, self.user)
        self.assertTrue(ok)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.agent_processed)
        self.assertTrue(self.ticket.agent_response.get("agent_fallback"))

    def test_agent_slo_endpoint_returns_metrics(self):
        resp = self.client.get("/api/monitoring/agent-slo/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("circuit_open", resp.data)
        self.assertIn("metrics", resp.data)

    def test_get_agent_slo_status_includes_success_rate(self):
        status = get_agent_slo_status()
        self.assertIn("http_timeout_seconds", status)
        self.assertEqual(status["http_timeout_seconds"], 30)
