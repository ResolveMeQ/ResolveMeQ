from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from integrations.models import ConnectorActionLog, OktaInstallation
from tickets.models import Ticket
from workflows.models import WorkflowTemplate
from workflows.services import start_workflow

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class WorkflowAutoActionLifecycleTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="offboard1", email="leaver@example.com", password="pw")
        self.staff = User.objects.create_user(username="itstaff1", email="it@example.com", password="pw")
        self.team = Team.objects.create(name="Offboarding Co", owner=self.owner)
        self.team.members.add(self.owner, self.staff)
        _set_active_team(self.staff, self.team)
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
            name="Offboarding test",
            trigger_category="offboarding",
            team=None,
            steps=[
                {
                    "title": "Deactivate Okta account",
                    "description": "",
                    "assignee_team": "IT",
                    "assignee_role": "it",
                    "step_type": "auto_action",
                    "due_days": 1,
                    "auto_action": {
                        "connector": "okta",
                        "action": "deactivate_user",
                        "email_from": "ticket_reporter",
                    },
                },
                {"title": "Next step", "description": "", "assignee_team": "IT", "step_type": "manual", "due_days": 1},
            ],
        )
        self.ticket = Ticket.objects.create(
            user=self.owner, team=self.team, issue_type="Offboard", category="offboarding", status="new"
        )
        self.workflow = start_workflow(template=self.template, ticket=self.ticket, team=self.team, started_by=self.owner)
        self.step = self.workflow.steps.order_by("order_index").first()
        self.url = f"/api/workflows/{self.workflow.id}/steps/{self.step.id}/auto-action/"
        self.client = APIClient()

    def test_auto_action_step_does_not_run_automatically(self):
        # Unlike auto_check, starting the workflow must NOT execute the write action.
        self.step.refresh_from_db()
        self.assertEqual(self.step.status, "active")
        self.assertFalse(ConnectorActionLog.objects.filter(workflow_step=self.step).exists())

    def test_execute_requires_confirm_flag(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.step.refresh_from_db()
        self.assertEqual(self.step.status, "active")

    @patch("integrations.connectors.okta.run_okta_action")
    def test_execute_success_marks_step_done_and_logs_executor(self, mock_action):
        mock_action.return_value = (True, "Okta user leaver@example.com deactivated.", {"email": "leaver@example.com"})
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["passed"])
        self.step.refresh_from_db()
        self.assertEqual(self.step.status, "done")
        log = ConnectorActionLog.objects.get(workflow_step=self.step)
        self.assertEqual(log.status, "success")
        self.assertEqual(log.executed_by_id, self.staff.pk)
        # Next step activated.
        next_step = self.workflow.steps.order_by("order_index")[1]
        next_step.refresh_from_db()
        self.assertEqual(next_step.status, "active")

    @patch("integrations.connectors.okta.run_okta_action")
    def test_execute_failure_leaves_step_active(self, mock_action):
        mock_action.return_value = (False, "No Okta user with email leaver@example.com.", {"email": "leaver@example.com"})
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["passed"])
        self.step.refresh_from_db()
        self.assertEqual(self.step.status, "active")

    def test_execute_forbidden_for_user_without_workflow_access(self):
        outsider = User.objects.create_user(username="outsider1", email="outsider@example.com", password="pw")
        self.client.force_authenticate(outsider)
        resp = self.client.post(self.url, {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_execute_rejects_non_active_step(self):
        next_step = self.workflow.steps.order_by("order_index")[1]
        url = f"/api/workflows/{self.workflow.id}/steps/{next_step.id}/auto-action/"
        self.client.force_authenticate(self.staff)
        resp = self.client.post(url, {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 400)  # manual step, not auto_action


class WorkflowAutoActionGeneratedPasswordTest(TestCase):
    """Reset-password actions must surface the one-time secret in the response but never persist it."""

    def setUp(self):
        self.owner = User.objects.create_user(username="offboard2", email="leaver2@example.com", password="pw")
        self.staff = User.objects.create_user(username="itstaff2", email="it2@example.com", password="pw")
        self.team = Team.objects.create(name="Offboarding Co 2", owner=self.owner)
        self.team.members.add(self.owner, self.staff)
        _set_active_team(self.staff, self.team)
        OktaInstallation.objects.create(
            resolvemeq_team=self.team,
            okta_domain="dev-456",
            issuer_url="https://dev-456.okta.com/oauth2/default",
            access_token="token",
            refresh_token="refresh",
            is_active=True,
            installed_by=self.owner,
        )
        self.template = WorkflowTemplate.objects.create(
            name="Reset test",
            trigger_category="offboarding",
            team=None,
            steps=[
                {
                    "title": "Reset password",
                    "description": "",
                    "assignee_team": "IT",
                    "assignee_role": "it",
                    "step_type": "auto_action",
                    "due_days": 1,
                    "auto_action": {
                        "connector": "okta",
                        "action": "reset_password",
                        "email_from": "ticket_reporter",
                    },
                },
            ],
        )
        self.ticket = Ticket.objects.create(
            user=self.owner, team=self.team, issue_type="Reset", category="offboarding", status="new"
        )
        self.workflow = start_workflow(template=self.template, ticket=self.ticket, team=self.team, started_by=self.owner)
        self.step = self.workflow.steps.order_by("order_index").first()
        self.url = f"/api/workflows/{self.workflow.id}/steps/{self.step.id}/auto-action/"
        self.client = APIClient()

    @patch("integrations.connectors.okta.run_okta_action")
    def test_generated_password_returned_but_not_persisted(self, mock_action):
        mock_action.return_value = (
            True,
            "Password reset for Okta user.",
            {"email": "leaver2@example.com", "temp_password": "Sup3r$ecretPW"},
        )
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("generated_password"), "Sup3r$ecretPW")
        log = ConnectorActionLog.objects.get(workflow_step=self.step)
        self.assertNotIn("temp_password", log.detail)
        self.assertNotIn("Sup3r$ecretPW", log.message)
