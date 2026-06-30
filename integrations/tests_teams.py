import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from base.models import Team, User
from integrations.models import TeamsInstallation, TeamsLinkCode
from tickets.models import Ticket


def _activity(**overrides):
    base = {
        "type": "message",
        "serviceUrl": "https://smba.trafficmanager.net/amer/",
        "channelId": "msteams",
        "from": {"id": "29:abc", "aadObjectId": "aad-user-1", "name": "Jane Doe"},
        "conversation": {"id": "19:conv1@thread.tacv2"},
        "recipient": {"id": "28:bot-id"},
        "channelData": {
            "tenant": {"id": "tenant-1"},
            "team": {"id": "19:team1@thread.tacv2"},
        },
    }
    base.update(overrides)
    return base


@override_settings(TEAMS_APP_ID="test-app-id", TEAMS_APP_PASSWORD="test-app-password")
class TeamsIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()
        self.messages_url = reverse("teams_messages")
        self.status_url = reverse("teams_integration_status")
        self.disconnect_url = reverse("teams_disconnect")
        self.link_start_url = reverse("teams_link_start")

        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pass12345",
        )
        self.team = Team.objects.create(name="Test Team", owner=self.owner)
        self.team.members.add(self.owner)

        self.teams_user = User.objects.create_user(
            username="aad-user-1", email="jane@example.com", password="unused",
        )
        from base.models import Profile

        profile, _ = Profile.objects.get_or_create(user=self.teams_user)
        profile.teams_aad_object_id = "aad-user-1"
        profile.teams_tenant_id = "tenant-1"
        profile.save(update_fields=["teams_aad_object_id", "teams_tenant_id"])

        self.installation = TeamsInstallation.objects.create(
            tenant_id="tenant-1",
            teams_team_id="19:team1@thread.tacv2",
            conversation_id="19:conv1@thread.tacv2",
            service_url="https://smba.trafficmanager.net/amer/",
            resolvemeq_team=self.team,
            installed_by=self.owner,
            is_active=True,
        )

    def _post(self, body):
        return self.client.post(
            self.messages_url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer faketoken",
        )

    # 1. Invalid/missing auth -> 401
    @patch("botframework.connector.auth.JwtTokenValidation.authenticate_request")
    def test_messages_endpoint_rejects_invalid_auth(self, mock_auth):
        mock_auth.side_effect = Exception("invalid token")
        response = self._post(_activity(text="status"))
        self.assertEqual(response.status_code, 401)

    def test_messages_endpoint_rejects_missing_auth_header(self):
        response = self.client.post(
            self.messages_url,
            data=json.dumps(_activity(text="status")),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    # 2. Link-code generation + consumption
    @patch("integrations.teams_views.verify_teams_request", return_value=True)
    @patch("integrations.teams_bot.teams_api_post_activity", return_value={})
    def test_link_code_consumption_links_installation(self, mock_send, _mock_verify):
        self.api_client.force_authenticate(user=self.owner)
        start_resp = self.api_client.get(f"{self.link_start_url}?team_id={self.team.id}")
        self.assertEqual(start_resp.status_code, 200)
        code = start_resp.json()["code"]

        new_team_id = "19:newteam@thread.tacv2"
        response = self._post(_activity(
            text=f"link {code}",
            channelData={"tenant": {"id": "tenant-2"}, "team": {"id": new_team_id}},
            conversation={"id": "19:newconv@thread.tacv2"},
        ))
        self.assertEqual(response.status_code, 200)

        link = TeamsLinkCode.objects.get(code=code)
        self.assertIsNotNone(link.consumed_at)
        inst = TeamsInstallation.objects.get(tenant_id="tenant-2", teams_team_id=new_team_id)
        self.assertEqual(inst.resolvemeq_team_id, self.team.id)

    # 3. Expired code
    @patch("integrations.teams_views.verify_teams_request", return_value=True)
    @patch("integrations.teams_bot.teams_api_post_activity", return_value={})
    def test_expired_link_code_rejected(self, mock_send, _mock_verify):
        link = TeamsLinkCode.objects.create(
            code="EXPIRED1",
            resolvemeq_team=self.team,
            created_by=self.owner,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        new_team_id = "19:anotherteam@thread.tacv2"
        response = self._post(_activity(
            text="link EXPIRED1",
            channelData={"tenant": {"id": "tenant-3"}, "team": {"id": new_team_id}},
            conversation={"id": "19:anotherconv@thread.tacv2"},
        ))
        self.assertEqual(response.status_code, 200)
        link.refresh_from_db()
        self.assertIsNone(link.consumed_at)
        self.assertFalse(
            TeamsInstallation.objects.filter(tenant_id="tenant-3", teams_team_id=new_team_id).exists()
        )

    # 4. conversationUpdate with bot added
    @patch("integrations.teams_views.verify_teams_request", return_value=True)
    def test_conversation_update_creates_unlinked_installation(self, _mock_verify):
        new_team_id = "19:freshteam@thread.tacv2"
        response = self._post(_activity(
            type="conversationUpdate",
            channelData={"tenant": {"id": "tenant-4"}, "team": {"id": new_team_id}},
            conversation={"id": "19:freshconv@thread.tacv2"},
            membersAdded=[{"id": "28:bot-id"}],
        ))
        self.assertEqual(response.status_code, 200)
        inst = TeamsInstallation.objects.get(tenant_id="tenant-4", teams_team_id=new_team_id)
        self.assertIsNone(inst.resolvemeq_team_id)
        self.assertTrue(inst.is_active)

    # 5. Escalate button
    @patch("integrations.teams_views.verify_teams_request", return_value=True)
    @patch("integrations.teams_bot.teams_api_post_activity", return_value={})
    @patch("tickets.tasks.handle_escalate")
    def test_escalate_action_calls_handle_escalate(self, mock_escalate, mock_send, _mock_verify):
        mock_escalate.return_value = True
        ticket = Ticket.objects.create(
            user=self.teams_user, team=self.team, issue_type="Printer (high)",
            status="open", description="jam",
        )
        response = self._post(_activity(
            text="",
            value={"action": "escalate_ticket", "ticket_id": str(ticket.ticket_id)},
        ))
        self.assertEqual(response.status_code, 200)
        mock_escalate.assert_called_once()

    # 6. Disconnect
    def test_disconnect_deactivates_installation(self):
        self.api_client.force_authenticate(user=self.owner)
        response = self.api_client.post(
            self.disconnect_url, {"team_id": str(self.team.id)}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("disconnected"))
        self.installation.refresh_from_db()
        self.assertFalse(self.installation.is_active)

    # 7. Ticket creation via card submit
    @patch("integrations.teams_views.verify_teams_request", return_value=True)
    @patch("integrations.teams_bot.get_teams_member_email", return_value=("jane@example.com", "Jane Doe"))
    @patch("integrations.teams_bot.teams_api_post_activity")
    def test_create_ticket_card_submit_creates_ticket(self, mock_post_activity, _mock_email, _mock_verify):
        mock_post_activity.return_value = {"id": "29:abc"}
        response = self._post(_activity(
            text="",
            value={
                "action": "create_ticket",
                "subject": "Laptop won't boot",
                "category": "hardware",
                "urgency": "high",
                "description": "Black screen on startup",
            },
        ))
        self.assertEqual(response.status_code, 200)
        ticket = Ticket.objects.filter(user=self.teams_user).order_by("-created_at").first()
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.team_id, self.team.id)
        self.assertIn("Laptop won't boot", ticket.issue_type)

    # 8. status command, team-scoped
    @patch("integrations.teams_views.verify_teams_request", return_value=True)
    @patch("integrations.teams_bot.get_teams_member_email", return_value=("jane@example.com", "Jane Doe"))
    @patch("integrations.teams_bot.teams_api_post_activity")
    def test_status_command_is_team_scoped(self, mock_post_activity, _mock_email, _mock_verify):
        mock_post_activity.return_value = {}
        other_owner = User.objects.create_user(
            username="other_owner", email="other@example.com", password="pass12345",
        )
        other_team = Team.objects.create(name="Other Team", owner=other_owner)
        Ticket.objects.create(
            user=self.teams_user, team=self.team, issue_type="My team ticket",
            status="open", description="x",
        )
        Ticket.objects.create(
            user=self.teams_user, team=other_team, issue_type="Other team ticket",
            status="open", description="x",
        )
        response = self._post(_activity(text="status"))
        self.assertEqual(response.status_code, 200)
        mock_post_activity.assert_called_once()
        sent_activity = mock_post_activity.call_args[0][2]
        text = sent_activity.get("text", "")
        self.assertIn("My team ticket", text)
        self.assertNotIn("Other team ticket", text)
