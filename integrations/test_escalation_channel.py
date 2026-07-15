from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from base.models import Team, User
from integrations import slack_installation as slack_inst
from integrations.models import SlackToken
from integrations.views import notify_support_escalation_slack
from tickets.models import Ticket


@override_settings(SLACK_ESCALATION_CHANNEL="C_GLOBAL_DEFAULT")
class EscalationChannelResolutionTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", email="owner1@example.com", password="x")
        self.team = Team.objects.create(name="Team A", owner=self.owner)
        self.team.members.add(self.owner)
        self.install = SlackToken.objects.create(
            team_id="TTEAMA",
            access_token="xoxb-a",
            resolvemeq_team=self.team,
            is_active=True,
        )

    def test_falls_back_to_global_setting_when_unset(self):
        self.assertEqual(slack_inst.escalation_channel_id(self.install), "C_GLOBAL_DEFAULT")

    def test_prefers_per_team_channel_when_set(self):
        self.install.escalation_channel_id = "C_TEAM_A_OPS"
        self.install.save(update_fields=["escalation_channel_id"])
        self.assertEqual(slack_inst.escalation_channel_id(self.install), "C_TEAM_A_OPS")

    def test_no_installation_falls_back_to_global(self):
        self.assertEqual(slack_inst.escalation_channel_id(None), "C_GLOBAL_DEFAULT")


@override_settings(SLACK_ESCALATION_CHANNEL="C_GLOBAL_DEFAULT")
class NotifySupportEscalationSlackTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner2", email="owner2@example.com", password="x")
        self.team = Team.objects.create(name="Team B", owner=self.owner)
        self.team.members.add(self.owner)
        self.install = SlackToken.objects.create(
            team_id="TTEAMB",
            access_token="xoxb-b",
            resolvemeq_team=self.team,
            escalation_channel_id="C_TEAM_B_OPS",
            is_active=True,
        )
        self.ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="VPN down",
            description="cannot connect",
            category="vpn",
            status="escalated",
        )

    @patch("integrations.views.slack_inst.slack_api_post")
    def test_posts_to_team_specific_channel(self, mock_post):
        mock_post.return_value = MagicMock()
        notify_support_escalation_slack(self.ticket, {"conversation_summary": "context"})
        mock_post.assert_called_once()
        _, kwargs_or_args = mock_post.call_args[0], mock_post.call_args[1]
        payload = mock_post.call_args[0][2]
        self.assertEqual(payload["channel"], "C_TEAM_B_OPS")

    @patch("integrations.views.slack_inst.slack_api_post")
    def test_falls_back_to_global_channel_when_team_channel_unset(self, mock_post):
        self.install.escalation_channel_id = ""
        self.install.save(update_fields=["escalation_channel_id"])
        mock_post.return_value = MagicMock()
        notify_support_escalation_slack(self.ticket, {"conversation_summary": "context"})
        mock_post.assert_called_once()
        payload = mock_post.call_args[0][2]
        self.assertEqual(payload["channel"], "C_GLOBAL_DEFAULT")


class SlackUpdateSettingsViewTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner3", email="owner3@example.com", password="x")
        self.member = User.objects.create_user(username="member3", email="member3@example.com", password="x")
        self.team = Team.objects.create(name="Team C", owner=self.owner)
        self.team.members.add(self.owner, self.member)
        self.install = SlackToken.objects.create(
            team_id="TTEAMC",
            access_token="xoxb-c",
            resolvemeq_team=self.team,
            is_active=True,
        )
        self.client = APIClient()
        self.url = reverse("slack_update_settings")

    def test_owner_can_set_escalation_channel(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.patch(
            self.url, {"team_id": str(self.team.id), "escalation_channel_id": "C_NEW_CHANNEL"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["escalation_channel_id"], "C_NEW_CHANNEL")
        self.install.refresh_from_db()
        self.assertEqual(self.install.escalation_channel_id, "C_NEW_CHANNEL")

    def test_non_owner_member_forbidden(self):
        self.client.force_authenticate(self.member)
        resp = self.client.patch(
            self.url, {"team_id": str(self.team.id), "escalation_channel_id": "C_NEW_CHANNEL"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_status_endpoint_reports_channel(self):
        self.install.escalation_channel_id = "C_EXISTING"
        self.install.save(update_fields=["escalation_channel_id"])
        self.client.force_authenticate(self.owner)
        resp = self.client.get(reverse("slack_integration_status"), {"team_id": str(self.team.id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["escalation_channel_id"], "C_EXISTING")
