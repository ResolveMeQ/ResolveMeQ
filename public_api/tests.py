from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from public_api.models import PartnerApiKey, generate_partner_key_pair
from tickets.models import Ticket

User = get_user_model()


class PublicApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="powner", email="owner@partner.test", password="x")
        self.team = Team.objects.create(name="Partner Co", owner=self.owner, is_active=True)
        self.team.members.add(self.owner)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.owner)
        prefs.active_team = self.team
        prefs.save()

        raw, prefix, hashed = generate_partner_key_pair()
        self.raw_key = raw
        self.api_key = PartnerApiKey.objects.create(
            team=self.team,
            name="Zapier",
            key_prefix=prefix,
            key_hash=hashed,
            scopes=["tickets:read", "tickets:write", "workflows:read", "rules:read"],
            created_by=self.owner,
        )
        self.partner = APIClient()
        self.partner.credentials(HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")
        self.owner_client = APIClient()
        self.owner_client.force_authenticate(self.owner)

    def test_owner_can_create_partner_key(self):
        resp = self.owner_client.post(
            "/api/public/keys/",
            {"name": "Make.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("api_key", resp.data["key"])
        self.assertTrue(resp.data["key"]["api_key"].startswith("rmq_pk_"))

    def test_partner_can_create_ticket(self):
        resp = self.partner.post(
            "/api/public/v1/tickets/create/",
            {
                "reporter_email": "newhire@customer.com",
                "issue_type": "Laptop setup",
                "description": "Need MacBook",
                "category": "hardware",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Ticket.objects.filter(team=self.team).count(), 1)

    def test_partner_can_list_tickets(self):
        Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="Test",
            status="open",
            category="other",
            description="x",
        )
        resp = self.partner.get("/api/public/v1/tickets/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 1)

    def test_invalid_key_rejected(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer rmq_pk_invalid")
        resp = client.get("/api/public/v1/tickets/")
        self.assertIn(resp.status_code, (401, 403))

    def test_scope_enforced(self):
        self.api_key.scopes = ["tickets:read"]
        self.api_key.save()
        resp = self.partner.post(
            "/api/public/v1/tickets/create/",
            {"reporter_email": "a@b.com", "issue_type": "X", "description": "y"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_api_info_lists_webhook_events(self):
        resp = self.partner.get("/api/public/v1/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("webhook_events", resp.data)
