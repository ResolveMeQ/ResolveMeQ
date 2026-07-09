from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from integrations.connectors.google_workspace import run_google_check, user_exists_by_email as google_user_exists
from integrations.connectors.microsoft365 import run_microsoft_check, user_exists_by_email as ms_user_exists
from integrations.models import GoogleWorkspaceInstallation, Microsoft365Installation
from workflows.auto_checks import run_auto_check
from workflows.models import WorkflowTemplate
from workflows.services import start_workflow

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


@override_settings(
    GOOGLE_WORKSPACE_CLIENT_ID="g-id",
    GOOGLE_WORKSPACE_CLIENT_SECRET="g-secret",
    GOOGLE_WORKSPACE_REDIRECT_URI="http://test/google/redirect",
)
class GoogleWorkspaceApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="gw1", email="gw1@example.com", password="pw")
        self.team = Team.objects.create(name="GW Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_status_not_connected(self):
        resp = self.client.get("/api/integrations/google/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["connected"])

    def test_oauth_start_returns_url(self):
        resp = self.client.get("/api/integrations/google/oauth/start/?format=json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("accounts.google.com", resp.data["authorize_url"])


@override_settings(
    MICROSOFT365_CLIENT_ID="m-id",
    MICROSOFT365_CLIENT_SECRET="m-secret",
    MICROSOFT365_REDIRECT_URI="http://test/microsoft/redirect",
)
class Microsoft365ApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ms1", email="ms1@example.com", password="pw")
        self.team = Team.objects.create(name="MS Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_status_not_connected(self):
        resp = self.client.get("/api/integrations/microsoft/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["connected"])

    def test_oauth_start_returns_url(self):
        resp = self.client.get("/api/integrations/microsoft/oauth/start/?format=json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("login.microsoftonline.com", resp.data["authorize_url"])


class GoogleMicrosoftConnectorTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="idp2", email="hire@example.com", password="pw")
        self.team = Team.objects.create(name="IdP Co", owner=self.owner)
        GoogleWorkspaceInstallation.objects.create(
            resolvemeq_team=self.team,
            access_token="g-token",
            refresh_token="g-refresh",
            is_active=True,
            installed_by=self.owner,
        )
        Microsoft365Installation.objects.create(
            resolvemeq_team=self.team,
            tenant_id="tenant-1",
            access_token="m-token",
            refresh_token="m-refresh",
            is_active=True,
            installed_by=self.owner,
        )

    @patch("integrations.connectors.google_workspace.google_api_get")
    def test_google_user_exists(self, mock_get):
        mock_get.return_value = {"primaryEmail": "hire@example.com", "suspended": False}
        inst = GoogleWorkspaceInstallation.objects.first()
        ok, msg = google_user_exists(inst, "hire@example.com")
        self.assertTrue(ok)

    @patch("integrations.connectors.microsoft365.graph_api_get")
    def test_microsoft_user_exists(self, mock_get):
        mock_get.return_value = {"id": "u1", "accountEnabled": True}
        inst = Microsoft365Installation.objects.first()
        ok, msg = ms_user_exists(inst, "hire@example.com")
        self.assertTrue(ok)

    @patch("integrations.connectors.google_workspace.run_google_check")
    def test_workflow_google_auto_check_advances(self, mock_check):
        from tickets.models import Ticket

        mock_check.return_value = (True, "Google user found.", {"email": "hire@example.com"})
        template = WorkflowTemplate.objects.create(
            name="GW check",
            trigger_category="onboarding",
            team=None,
            steps=[{
                "title": "Verify Google",
                "assignee_team": "IT",
                "step_type": "auto_check",
                "auto_check": {"connector": "google_workspace", "check": "user_exists", "email_from": "ticket_reporter"},
            }],
        )
        ticket = Ticket.objects.create(user=self.owner, team=self.team, issue_type="Hire", category="onboarding", status="new")
        workflow = start_workflow(template=template, ticket=ticket, team=self.team, started_by=self.owner)
        step = workflow.steps.first()
        self.assertEqual(step.status, "done")
