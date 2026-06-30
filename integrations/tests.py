import json
import time
import hmac
import hashlib
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from base.models import Team, User
from integrations.models import SlackToken
from tickets.models import Ticket


def slack_signature(secret, body, timestamp):
    sig_basestring = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()


@override_settings(SLACK_SIGNING_SECRET="testsecret")
class SlackIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()
        self.signing_secret = "testsecret"
        self.timestamp = str(int(time.time()))
        self.oauth_url = reverse("slack_oauth_redirect")
        self.events_url = reverse("slack_events")
        self.commands_url = reverse("slack_slash_command")
        self.actions_url = reverse("slack_interactive_action")

        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass12345",
        )
        self.team = Team.objects.create(name="Test Team", owner=self.owner)
        self.team.members.add(self.owner)
        self.slack_install = SlackToken.objects.create(
            team_id="TTESTWORKSPACE",
            access_token="xoxb-test",
            bot_user_id="BTEST",
            resolvemeq_team=self.team,
            installed_by=self.owner,
            is_active=True,
        )
        self.slack_user = User.objects.create_user(
            username="U01234567",
            email="U01234567@slack.local",
            password="unused",
        )

    def _signed_post(self, url, body, content_type="application/json"):
        signature = slack_signature(self.signing_secret, body, self.timestamp)
        return self.client.post(
            url,
            data=body,
            content_type=content_type,
            HTTP_X_SLACK_REQUEST_TIMESTAMP=self.timestamp,
            HTTP_X_SLACK_SIGNATURE=signature,
        )

    def test_slack_oauth_redirect_missing_code(self):
        response = self.client.get(self.oauth_url)
        self.assertEqual(response.status_code, 400)

    def test_slack_events_url_verification(self):
        payload = {"type": "url_verification", "challenge": "test_challenge"}
        body = json.dumps(payload)
        response = self._signed_post(self.events_url, body)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"challenge": "test_challenge"})

    def test_slack_events_invalid_signature(self):
        payload = {"type": "url_verification", "challenge": "test_challenge"}
        body = json.dumps(payload)
        response = self.client.post(
            self.events_url,
            data=body,
            content_type="application/json",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=self.timestamp,
            HTTP_X_SLACK_SIGNATURE="v0=invalidsignature",
        )
        self.assertEqual(response.status_code, 403)

    @patch("integrations.slack_installation.slack_api_post")
    def test_slack_events_message_does_not_auto_reply(self, mock_post):
        payload = {
            "type": "event_callback",
            "team_id": "TTESTWORKSPACE",
            "event": {"type": "message", "channel": "C123", "text": "hello"},
        }
        body = json.dumps(payload)
        response = self._signed_post(self.events_url, body)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_not_called()

    def test_slack_slash_command_status_scoped_to_team(self):
        Ticket.objects.create(
            user=self.slack_user,
            team=self.team,
            issue_type="VPN (medium)",
            status="open",
            description="test",
        )
        other_team = Team.objects.create(name="Other", owner=self.owner)
        Ticket.objects.create(
            user=self.slack_user,
            team=other_team,
            issue_type="Email (low)",
            status="open",
            description="other team",
        )
        data = {
            "command": "/resolvemeq",
            "text": "status",
            "user_id": "U01234567",
            "team_id": "TTESTWORKSPACE",
            "trigger_id": "testtrigger",
        }
        body = "&".join([f"{k}={v}" for k, v in data.items()])
        signature = slack_signature(self.signing_secret, body, self.timestamp)
        response = self.client.post(
            self.commands_url,
            data=body,
            content_type="application/x-www-form-urlencoded",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=self.timestamp,
            HTTP_X_SLACK_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("VPN", content)
        self.assertNotIn("Email", content)

    @patch("tickets.tasks.handle_escalate")
    def test_slack_escalate_button_calls_handle_escalate(self, mock_escalate):
        mock_escalate.return_value = True
        ticket = Ticket.objects.create(
            user=self.slack_user,
            team=self.team,
            issue_type="Printer (high)",
            status="open",
            description="jam",
        )
        payload = {
            "type": "block_actions",
            "team": {"id": "TTESTWORKSPACE"},
            "user": {"id": "U01234567"},
            "response_url": "https://hooks.slack.com/actions/T/123",
            "actions": [
                {
                    "action_id": "escalate_ticket",
                    "value": f"escalate_{ticket.ticket_id}",
                }
            ],
        }
        body = f"payload={json.dumps(payload)}"
        with patch("integrations.views.requests.post") as mock_resp_post:
            mock_resp_post.return_value = MagicMock(ok=True)
            signature = slack_signature(self.signing_secret, body, self.timestamp)
            response = self.client.post(
                self.actions_url,
                data=body,
                content_type="application/x-www-form-urlencoded",
                HTTP_X_SLACK_REQUEST_TIMESTAMP=self.timestamp,
                HTTP_X_SLACK_SIGNATURE=signature,
            )
        self.assertEqual(response.status_code, 200)
        mock_escalate.assert_called_once()
        args, kwargs = mock_escalate.call_args
        self.assertEqual(args[0].ticket_id, ticket.ticket_id)

    def test_slack_disconnect_deactivates_install(self):
        self.api_client.force_authenticate(user=self.owner)
        response = self.api_client.post(
            reverse("slack_disconnect"),
            {"team_id": str(self.team.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("disconnected"))
        self.slack_install.refresh_from_db()
        self.assertFalse(self.slack_install.is_active)
