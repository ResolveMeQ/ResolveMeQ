"""Tests for automation notify actions."""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from automation.actions import execute_actions
from automation.validation import normalize_actions
from base.models import Plan, Subscription, Team
from tickets.models import Ticket

User = get_user_model()


@override_settings(
    SLACK_ESCALATION_CHANNEL="C_TESTOPS",
    FRONTEND_URL="https://app.test",
)
class AutomationNotifyActionTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="notify1", email="notify1@example.com", password="pw")
        self.team = Team.objects.create(name="Notify Co", owner=self.owner)
        self.team.members.add(self.owner)
        plan = Plan.objects.create(name="Notify Plan", slug="notify-plan", max_members=20)
        Subscription.objects.create(user=self.owner, plan=plan, status="trial")
        self.ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="VPN down",
            description="Cannot connect",
            category="vpn",
            status="new",
        )

    @patch("integrations.views.notify_support_escalation_slack")
    def test_notify_slack_posts_for_ticket(self, mock_slack):
        actions = normalize_actions([{"type": "notify_slack", "message": "Security review needed"}])
        status, messages = execute_actions(actions, {"ticket": self.ticket})
        self.assertEqual(status, "success")
        mock_slack.assert_called_once()
        self.assertIn("Slack", messages[0])

    @patch("integrations.slack_installation.slack_api_post")
    @patch("integrations.slack_installation.get_installation_for_team")
    def test_notify_slack_channel_override(self, mock_inst, mock_post):
        mock_inst.return_value = MagicMock()
        mock_post.return_value = MagicMock()
        actions = normalize_actions([
            {"type": "notify_slack", "channel_id": "C_CUSTOM", "message": "Hello ops"},
        ])
        status, messages = execute_actions(actions, {"ticket": self.ticket, "team": self.team})
        self.assertEqual(status, "success")
        mock_post.assert_called_once()

    @patch("integrations.teams_views.notify_support_escalation_teams")
    def test_notify_teams_posts_for_ticket(self, mock_teams):
        actions = normalize_actions([{"type": "notify_teams", "message": "Escalation alert"}])
        status, messages = execute_actions(actions, {"ticket": self.ticket})
        self.assertEqual(status, "success")
        mock_teams.assert_called_once()
        self.assertIn("Teams", messages[0])
