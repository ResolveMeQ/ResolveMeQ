from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.models import ResolutionTemplate
from workflows.models import Workflow, WorkflowStep, WorkflowStepAssistantEvent, WorkflowTemplate
from workflows.playbooks.employee_onboarding import (
    ONBOARDING_RESOLUTION_TEMPLATE,
    ONBOARDING_RESOLUTION_TEMPLATE_NAME,
    ONBOARDING_TEMPLATE_NAME,
)
from workflows.services import start_workflow
from workflows.template_validation import normalize_template_steps
from workflows.playbooks.employee_onboarding import ONBOARDING_TEMPLATE_STEPS

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class PlaybookBundleP3Test(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="p3b1", email="p3b1@example.com", password="pw")
        self.team = Team.objects.create(name="P3 Bundle Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        WorkflowTemplate.objects.update_or_create(
            name=ONBOARDING_TEMPLATE_NAME,
            team=None,
            defaults={
                "trigger_category": "onboarding",
                "steps": normalize_template_steps(ONBOARDING_TEMPLATE_STEPS),
            },
        )
        ResolutionTemplate.objects.create(
            name=ONBOARDING_RESOLUTION_TEMPLATE_NAME,
            **{k: v for k, v in ONBOARDING_RESOLUTION_TEMPLATE.items() if k != "name"},
        )

    def test_playbook_includes_resolution_template(self):
        resp = self.client.get("/api/workflows/playbooks/employee-onboarding/")
        self.assertEqual(resp.status_code, 200)
        pb = resp.data["playbook"]
        self.assertTrue(pb["resolution_template_installed"])
        self.assertEqual(pb["resolution_templates"][0]["name"], ONBOARDING_RESOLUTION_TEMPLATE_NAME)
        self.assertIn("install_playbook_bundle", pb["install_command"])


class StepAssistantTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="p3a1", email="p3a1@example.com", password="pw")
        self.team = Team.objects.create(name="P3 Assist Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.template = WorkflowTemplate.objects.create(
            name="Assist template",
            trigger_category="onboarding",
            team=None,
            steps=normalize_template_steps([
                {
                    "title": "Provision accounts",
                    "description": "Create email and SSO accounts.",
                    "assignee_team": "IT",
                    "assignee_role": "it",
                    "step_type": "manual",
                    "due_days": 1,
                    "kb_links": ["New Employee - IT Onboarding Checklist"],
                },
            ]),
        )
        self.workflow = start_workflow(template=self.template, team=self.team, started_by=self.owner)
        self.step = self.workflow.steps.get(order_index=0)

    @patch("workflows.step_assistant.try_consume_agent_operation")
    @patch("workflows.step_assistant.requests.post")
    def test_step_assistant_returns_llm_guidance(self, mock_post, mock_quota):
        mock_quota.return_value = MagicMock(allowed=True, used=1, limit=500)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "reasoning": "Start with SSO and email.",
            "confidence": 0.82,
            "solution": {"steps": ["Create Okta user", "Assign Google license"]},
            "kb_article_citations": [{"kb_id": "kb-1", "title": "Onboarding checklist"}],
        }
        mock_post.return_value = mock_resp

        resp = self.client.get(f"/api/workflows/{self.workflow.id}/steps/{self.step.id}/assistant/")
        self.assertEqual(resp.status_code, 200)
        suggestions = resp.data["suggestions"]
        self.assertEqual(suggestions["source"], "llm_kb")
        self.assertTrue(suggestions["actions"])
        self.assertTrue(
            WorkflowStepAssistantEvent.objects.filter(
                step=self.step,
                event_type=WorkflowStepAssistantEvent.EVENT_VIEWED,
            ).exists()
        )

    @patch("workflows.step_assistant.try_consume_agent_operation")
    @patch("workflows.step_assistant.requests.post")
    def test_step_assistant_fallback_when_agent_down(self, mock_post, mock_quota):
        mock_quota.return_value = MagicMock(allowed=True, used=1, limit=500)
        mock_post.side_effect = Exception("agent offline")

        resp = self.client.get(f"/api/workflows/{self.workflow.id}/steps/{self.step.id}/assistant/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["suggestions"]["source"], "fallback")
        self.assertFalse(resp.data["suggestions"]["agent_used"])

    def test_step_assistant_accept_logs_event(self):
        resp = self.client.post(
            f"/api/workflows/{self.workflow.id}/steps/{self.step.id}/assistant/accept/",
            {"note": "Created Okta user for hire@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["accepted"])
        self.assertTrue(
            WorkflowStepAssistantEvent.objects.filter(
                step=self.step,
                event_type=WorkflowStepAssistantEvent.EVENT_ACCEPTED,
            ).exists()
        )
