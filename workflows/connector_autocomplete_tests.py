from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from integrations.models import ConnectorCheckLog, GoogleWorkspaceInstallation, OktaInstallation
from tickets.models import Ticket
from workflows.models import WorkflowTemplate
from workflows.services import start_workflow
from workflows.template_validation import normalize_template_steps

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


ONBOARDING_AUTO_CHECK_STEPS = [
    {
        "title": "Provision accounts",
        "description": "Manual provisioning",
        "assignee_team": "IT",
        "assignee_role": "it",
        "step_type": "manual",
        "due_days": 1,
    },
    {
        "title": "Verify Okta SSO account",
        "description": "Auto check Okta",
        "assignee_team": "IT",
        "assignee_role": "it",
        "step_type": "auto_check",
        "due_days": 1,
        "auto_check": {"connector": "okta", "check": "user_exists", "email_from": "ticket_reporter"},
    },
    {
        "title": "Verify Google Workspace account",
        "description": "Auto check Google",
        "assignee_team": "IT",
        "assignee_role": "it",
        "step_type": "auto_check",
        "due_days": 1,
        "auto_check": {"connector": "google_workspace", "check": "user_exists", "email_from": "ticket_reporter"},
    },
    {
        "title": "Manager sign-off",
        "description": "HR approval",
        "assignee_team": "HR",
        "assignee_role": "hr",
        "step_type": "approval",
        "due_days": 2,
    },
]


class ConnectorAutoCompleteTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="p3c1",
            email="hire@example.com",
            password="pw",
        )
        self.team = Team.objects.create(name="AutoComplete Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        OktaInstallation.objects.create(
            resolvemeq_team=self.team,
            okta_domain="dev-123",
            issuer_url="https://dev-123.okta.com/oauth2/default",
            access_token="token",
            refresh_token="refresh",
            is_active=True,
            installed_by=self.owner,
        )
        GoogleWorkspaceInstallation.objects.create(
            resolvemeq_team=self.team,
            admin_email="admin@example.com",
            access_token="token",
            refresh_token="refresh",
            is_active=True,
            installed_by=self.owner,
        )
        self.template = WorkflowTemplate.objects.create(
            name="Onboarding auto",
            trigger_category="onboarding",
            team=None,
            steps=normalize_template_steps(ONBOARDING_AUTO_CHECK_STEPS),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    @patch("integrations.connectors.google_workspace.run_google_check")
    @patch("integrations.connectors.okta.run_okta_check")
    def test_connector_chain_auto_completes_on_manual_step_done(self, mock_okta, mock_google):
        mock_okta.return_value = (True, "Okta user found (ACTIVE).", {"email": "hire@example.com"})
        mock_google.return_value = (True, "Google user found.", {"email": "hire@example.com"})

        ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="New hire Jane",
            category="onboarding",
            status="new",
        )
        workflow = start_workflow(
            template=self.template,
            ticket=ticket,
            team=self.team,
            started_by=self.owner,
        )
        manual = workflow.steps.get(order_index=0)
        self.assertEqual(manual.status, "active")

        from django.utils import timezone

        manual.status = "done"
        manual.completed_at = timezone.now()
        manual.save(update_fields=["status", "completed_at"])
        from workflows.services import _activate_next_steps

        _activate_next_steps(workflow)
        workflow.refresh_from_db()

        okta = workflow.steps.get(order_index=1)
        google = workflow.steps.get(order_index=2)
        hr = workflow.steps.get(order_index=3)
        self.assertEqual(okta.status, "done")
        self.assertEqual(google.status, "done")
        self.assertEqual(hr.status, "active")
        self.assertEqual(
            ConnectorCheckLog.objects.filter(workflow=workflow, status="success").count(),
            2,
        )

    @patch("integrations.connectors.okta.run_okta_check")
    def test_connector_check_stays_active_when_not_connected(self, mock_okta):
        mock_okta.return_value = (False, "No Okta user.", {"email": "hire@example.com"})
        template = WorkflowTemplate.objects.create(
            name="Okta only",
            trigger_category="",
            team=None,
            steps=normalize_template_steps([ONBOARDING_AUTO_CHECK_STEPS[1]]),
        )
        workflow = start_workflow(template=template, team=self.team, started_by=self.owner)
        step = workflow.steps.get(order_index=0)
        self.assertEqual(step.status, "active")
        self.assertEqual(
            ConnectorCheckLog.objects.filter(workflow=workflow, connector="okta").count(),
            1,
        )

    @patch("integrations.connectors.google_workspace.run_google_check")
    @patch("integrations.connectors.okta.run_okta_check")
    def test_playbook_bundle_reports_connector_auto_steps(self, mock_okta, mock_google):
        from workflows.playbooks.employee_onboarding import ONBOARDING_TEMPLATE_NAME, ONBOARDING_TEMPLATE_STEPS

        WorkflowTemplate.objects.update_or_create(
            name=ONBOARDING_TEMPLATE_NAME,
            team=None,
            defaults={
                "trigger_category": "onboarding",
                "steps": normalize_template_steps(ONBOARDING_TEMPLATE_STEPS),
            },
        )
        resp = self.client.get("/api/workflows/playbooks/employee-onboarding/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["playbook"]["connector_auto_steps"], 3)

    @patch("integrations.connectors.okta.run_okta_check")
    def test_workflow_api_marks_auto_verified_steps(self, mock_okta):
        mock_okta.return_value = (True, "Okta user found.", {"email": "hire@example.com"})
        template = WorkflowTemplate.objects.create(
            name="Verify only",
            trigger_category="",
            team=None,
            steps=normalize_template_steps([ONBOARDING_AUTO_CHECK_STEPS[1]]),
        )
        ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="Hire",
            category="onboarding",
            status="new",
        )
        workflow = start_workflow(
            template=template,
            ticket=ticket,
            team=self.team,
            started_by=self.owner,
        )
        resp = self.client.get("/api/workflows/")
        wf = next(w for w in resp.data["workflows"] if w["id"] == str(workflow.id))
        step = wf["steps"][0]
        self.assertTrue(step["auto_verified"])
        self.assertEqual(step["auto_check_result"]["status"], "success")
