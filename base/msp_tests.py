from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.models import Ticket
from workflows.models import Workflow, WorkflowTemplate
from workflows.services import start_workflow

User = get_user_model()


class MspModeTest(TestCase):
    def setUp(self):
        self.msp_admin = User.objects.create_user(username="msp1", email="msp1@example.com", password="pw")
        self.hub = Team.objects.create(
            name="ResolveMeQ MSP",
            owner=self.msp_admin,
            team_kind=Team.TEAM_KIND_MSP,
        )
        self.hub.members.add(self.msp_admin)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.msp_admin)
        prefs.active_team = self.hub
        prefs.save()
        self.client = APIClient()
        self.client.force_authenticate(self.msp_admin)

    def test_enable_msp_on_workspace(self):
        ws = Team.objects.create(name="My IT Shop", owner=self.msp_admin)
        ws.members.add(self.msp_admin)
        resp = self.client.post("/api/msp/enable/", {"team_id": str(ws.id)}, format="json")
        self.assertEqual(resp.status_code, 201)
        ws.refresh_from_db()
        self.assertEqual(ws.team_kind, Team.TEAM_KIND_MSP)

    def test_create_client_workspace(self):
        resp = self.client.post(
            "/api/msp/clients/",
            {"team_id": str(self.hub.id), "name": "Acme Corp", "description": "Client A"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        client_id = resp.data["client"]["id"]
        client = Team.objects.get(pk=client_id)
        self.assertEqual(client.team_kind, Team.TEAM_KIND_MSP_CLIENT)
        self.assertEqual(client.msp_parent_id, self.hub.id)
        self.assertTrue(client.members.filter(pk=self.msp_admin.pk).exists())

    def test_dashboard_shows_client_usage(self):
        create = self.client.post(
            "/api/msp/clients/",
            {"team_id": str(self.hub.id), "name": "Beta Inc"},
            format="json",
        )
        client = Team.objects.get(pk=create.data["client"]["id"])
        Ticket.objects.create(user=self.msp_admin, team=client, issue_type="VPN", category="vpn", status="open")
        template = WorkflowTemplate.objects.create(name="T1", team=client, steps=[{"title": "S", "due_days": 1}])
        start_workflow(template=template, team=client, started_by=self.msp_admin)

        resp = self.client.get(f"/api/msp/dashboard/?team_id={self.hub.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["clients"]), 1)
        usage = resp.data["clients"][0]["usage"]
        self.assertGreaterEqual(usage["tickets_created_period"], 1)
        self.assertGreaterEqual(usage["workflows_started_period"], 1)

    def test_client_teams_isolated_by_team_id(self):
        create = self.client.post(
            "/api/msp/clients/",
            {"team_id": str(self.hub.id), "name": "Gamma LLC"},
            format="json",
        )
        client = Team.objects.get(pk=create.data["client"]["id"])
        Ticket.objects.create(user=self.msp_admin, team=client, issue_type="A", category="other", status="open")
        Ticket.objects.create(user=self.msp_admin, team=self.hub, issue_type="B", category="other", status="open")

        resp = self.client.get(f"/api/msp/clients/{client.id}/usage/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["usage"]["tickets_open"], 1)
