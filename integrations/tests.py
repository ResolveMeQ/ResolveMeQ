import json
import time
import hmac
import hashlib
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings

def slack_signature(secret, body, timestamp):
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return my_signature

class SlackIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signing_secret = "testsecret"
        # Override settings for tests
        settings.SLACK_SIGNING_SECRET = self.signing_secret
        self.timestamp = str(int(time.time()))
        self.oauth_url = reverse("slack_oauth_redirect")
        self.events_url = reverse("slack_events")
        self.commands_url = reverse("slack_slash_command")

    def test_slack_oauth_redirect_missing_code(self):
        response = self.client.get(self.oauth_url)
        self.assertEqual(response.status_code, 400)

    def test_slack_events_url_verification(self):
        payload = {"type": "url_verification", "challenge": "test_challenge"}
        body = json.dumps(payload)
        signature = slack_signature(self.signing_secret, body, self.timestamp)
        response = self.client.post(
            self.events_url,
            data=body,
            content_type="application/json",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=self.timestamp,
            HTTP_X_SLACK_SIGNATURE=signature,
        )
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

    def test_slack_slash_command_status(self):
        # Simulate a valid slash command for status
        from base.models import User
        user = User.objects.create_user(
            username="slackuser",
            email="slackuser@example.com",
            first_name="Slack",
            last_name="User"
        )
        data = {
            "command": "/resolvemeq",
            "text": "status",
            "user_id": str(user.pk),  # Use a valid UUID
            "trigger_id": "testtrigger",
        }
        body = "&".join([f"{k}={v}" for k, v in data.items()])
        signature = slack_signature(self.signing_secret, body, self.timestamp)
        response = self.client.post(
            self.commands_url,
            data=body,  # Send the raw body, not a dict
            content_type="application/x-www-form-urlencoded",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=self.timestamp,
            HTTP_X_SLACK_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("You have no tickets", response.content.decode())
