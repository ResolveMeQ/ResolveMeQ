import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from integrations.connectors.webhook import (
    build_event_payload,
    deliver_webhook_now,
    fan_out_webhook_event,
    generate_secret,
    sign_payload,
    verify_signature,
)
from integrations.models import WebhookDelivery, WebhookEndpoint
from tickets.services import create_ticket_with_reporter

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class WebhookSigningTest(TestCase):
    def test_sign_and_verify_round_trip(self):
        secret = generate_secret()
        body = json.dumps({"event": "ticket.created"}).encode("utf-8")
        signature, ts = sign_payload(secret, body)
        self.assertTrue(signature.startswith("v1="))
        self.assertTrue(
            verify_signature(secret, body, str(ts), signature)
        )

    def test_reject_tampered_body(self):
        secret = generate_secret()
        body = b'{"event":"ticket.created"}'
        signature, ts = sign_payload(secret, body)
        self.assertFalse(
            verify_signature(secret, b'{"event":"ticket.escalated"}', str(ts), signature)
        )


class WebhookDeliveryTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="wh1", email="wh1@example.com", password="pw")
        self.team = Team.objects.create(name="Webhook Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.endpoint = WebhookEndpoint.objects.create(
            resolvemeq_team=self.team,
            name="Make hook",
            url="https://hooks.example.com/inbound",
            secret=generate_secret(),
            events=["ticket.created"],
            created_by=self.owner,
        )

    @patch("integrations.connectors.webhook.http_post_json")
    def test_deliver_webhook_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"
        mock_post.return_value = mock_resp

        from tickets.models import Ticket

        ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="Test",
            category="wifi",
            status="new",
        )
        context = {
            "ticket": ticket,
            "team_id": str(self.team.pk),
            "category": ticket.category,
            "status": ticket.status,
        }
        ids = fan_out_webhook_event("ticket.created", context)
        self.assertEqual(len(ids), 1)
        delivery = WebhookDelivery.objects.get(pk=ids[0])
        self.assertEqual(delivery.status, "pending")
        ok = deliver_webhook_now(delivery.pk)
        self.assertTrue(ok)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "success")
        self.assertEqual(delivery.response_code, 200)
        mock_post.assert_called_once()
        headers = mock_post.call_args.kwargs["headers"]
        self.assertIn("X-ResolveMeq-Signature", headers)
        self.assertIn("X-ResolveMeq-Timestamp", headers)

    @patch("integrations.connectors.base.http_post_json")
    def test_event_filter_skips_non_matching_endpoint(self, mock_post):
        ticket = create_ticket_with_reporter(self.owner, self.team, issue_type="Test", category="wifi")
        context = {"ticket": ticket, "team_id": str(self.team.pk)}
        ids = fan_out_webhook_event("ticket.escalated", context)
        self.assertEqual(ids, [])
        mock_post.assert_not_called()

    def test_build_payload_shape(self):
        ticket = create_ticket_with_reporter(self.owner, self.team, issue_type="Hire", category="onboarding")
        payload = build_event_payload(
            "ticket.created",
            {"ticket": ticket, "team_id": str(self.team.pk)},
        )
        self.assertEqual(payload["event"], "ticket.created")
        self.assertEqual(payload["ticket"]["category"], "onboarding")


class WebhookApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="wh2", email="wh2@example.com", password="pw")
        self.member = User.objects.create_user(username="whmem", email="whmem@example.com", password="pw")
        self.team = Team.objects.create(name="Webhook API Co", owner=self.owner)
        self.team.members.add(self.owner, self.member)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_owner_can_create_and_list_webhooks(self):
        resp = self.client.post(
            "/api/integrations/webhooks/",
            {"name": "n8n", "url": "https://n8n.example.com/hook", "events": ["ticket.created"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("secret", resp.data["endpoint"])
        resp = self.client.get("/api/integrations/webhooks/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["can_manage"])
        self.assertEqual(len(resp.data["endpoints"]), 1)

    def test_member_cannot_create_webhook(self):
        self.client.force_authenticate(self.member)
        _set_active_team(self.member, self.team)
        resp = self.client.post(
            "/api/integrations/webhooks/",
            {"url": "https://n8n.example.com/hook"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    @patch("integrations.connectors.webhook.http_post_json")
    def test_test_delivery_endpoint(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.text = "accepted"
        mock_post.return_value = mock_resp

        create = self.client.post(
            "/api/integrations/webhooks/",
            {"url": "https://hooks.example.com/test"},
            format="json",
        )
        endpoint_id = create.data["endpoint"]["id"]
        resp = self.client.post(
            f"/api/integrations/webhooks/{endpoint_id}/test/",
            {"event_type": "ticket.created"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["delivery"]["status"], "success")
