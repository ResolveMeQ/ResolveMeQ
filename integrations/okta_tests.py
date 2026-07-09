from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from integrations.connectors.okta import normalize_okta_domain, user_exists_by_email
from integrations.models import ConnectorCheckLog, OktaInstallation
from workflows.auto_checks import run_auto_check
from workflows.models import WorkflowTemplate
from workflows.services import start_workflow

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class OktaConnectorTest(TestCase):
    def test_normalize_okta_domain(self):
        self.assertEqual(normalize_okta_domain("https://dev-123.okta.com"), "dev-123")
        self.assertEqual(normalize_okta_domain("dev-123"), "dev-123")

    @patch("integrations.connectors.okta.okta_api_get")
    def test_user_exists_by_email_found(self, mock_get):
        mock_get.return_value = [{"id": "00u1", "status": "ACTIVE"}]
        inst = OktaInstallation(
            okta_domain="dev-123",
            issuer_url="https://dev-123.okta.com/oauth2/default",
            access_token="token",
        )
        ok, msg = user_exists_by_email(inst, "hire@example.com")
        self.assertTrue(ok)
        self.assertIn("ACTIVE", msg)

    @patch("integrations.connectors.okta.okta_api_get")
    def test_user_exists_by_email_missing(self, mock_get):
        mock_get.return_value = []
        inst = OktaInstallation(
            okta_domain="dev-123",
            issuer_url="https://dev-123.okta.com/oauth2/default",
            access_token="token",
        )
        ok, msg = user_exists_by_email(inst, "missing@example.com")
        self.assertFalse(ok)


@override_settings(OKTA_CLIENT_ID="cid", OKTA_CLIENT_SECRET="secret", OKTA_REDIRECT_URI="http://test/redirect")
class OktaApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="okta1", email="okta1@example.com", password="pw")
        self.team = Team.objects.create(name="Okta Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_status_not_connected(self):
        resp = self.client.get("/api/integrations/okta/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["connected"])

    def test_oauth_start_requires_domain(self):
        resp = self.client.get("/api/integrations/okta/oauth/start/?format=json")
        self.assertEqual(resp.status_code, 400)

    def test_oauth_start_returns_authorize_url(self):
        resp = self.client.get("/api/integrations/okta/oauth/start/?format=json&okta_domain=dev-123")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("authorize_url", resp.data)
        self.assertIn("dev-123.okta.com", resp.data["authorize_url"])


class WorkflowAutoCheckTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="okta2", email="hire@example.com", password="pw")
        self.team = Team.objects.create(name="AutoCheck Co", owner=self.owner)
        self.team.members.add(self.owner)
        OktaInstallation.objects.create(
            resolvemeq_team=self.team,
            okta_domain="dev-123",
            issuer_url="https://dev-123.okta.com/oauth2/default",
            access_token="token",
            refresh_token="refresh",
            is_active=True,
            installed_by=self.owner,
        )
        self.template = WorkflowTemplate.objects.create(
            name="Onboarding test",
            trigger_category="onboarding",
            team=None,
            steps=[
                {
                    "title": "Verify Okta",
                    "description": "",
                    "assignee_team": "IT",
                    "assignee_role": "it",
                    "step_type": "auto_check",
                    "due_days": 1,
                    "auto_check": {
                        "connector": "okta",
                        "check": "user_exists",
                        "email_from": "ticket_reporter",
                    },
                },
                {"title": "Next step", "description": "", "assignee_team": "IT", "step_type": "manual", "due_days": 1},
            ],
        )

    @patch("integrations.connectors.okta.run_okta_check")
    def test_auto_check_pass_advances_workflow(self, mock_check):
        from tickets.models import Ticket

        mock_check.return_value = (True, "Okta user found (ACTIVE).", {"email": "hire@example.com"})
        ticket = Ticket.objects.create(user=self.owner, team=self.team, issue_type="Hire", category="onboarding", status="new")
        workflow = start_workflow(template=self.template, ticket=ticket, team=self.team, started_by=self.owner)
        steps = list(workflow.steps.order_by("order_index"))
        self.assertEqual(steps[0].status, "done")
        self.assertEqual(steps[1].status, "active")
        self.assertTrue(ConnectorCheckLog.objects.filter(workflow_step=steps[0], status="success").exists())

    @patch("integrations.connectors.okta.run_okta_check")
    def test_auto_check_fail_leaves_step_active(self, mock_check):
        from tickets.models import Ticket

        mock_check.return_value = (False, "No Okta user.", {"email": "hire@example.com"})
        ticket = Ticket.objects.create(user=self.owner, team=self.team, issue_type="Hire", category="onboarding", status="new")
        workflow = start_workflow(template=self.template, ticket=ticket, team=self.team, started_by=self.owner)
        step = workflow.steps.order_by("order_index").first()
        self.assertEqual(step.status, "active")
        passed, _ = run_auto_check(step, workflow)
        self.assertFalse(passed)
