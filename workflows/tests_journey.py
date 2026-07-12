"""End-to-end workflow journey: ticket → rule → workflow → claim → complete."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automation.models import Rule, RuleExecutionLog
from automation.validation import normalize_actions, normalize_conditions
from base.models import Plan, Subscription, Team, UserPreferences
from tickets.services import create_ticket_with_reporter
from workflows.models import Workflow, WorkflowStep, WorkflowTemplate

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class TicketWorkflowJourneyTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="journey", email="journey@example.com", password="pw")
        self.team = Team.objects.create(name="Journey Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        plan = Plan.objects.create(name="Journey Plan", slug="journey-plan", max_members=20)
        Subscription.objects.create(
            user=self.owner,
            plan=plan,
            status="trial",
        )
        self.template = WorkflowTemplate.objects.create(
            name="Onboarding journey",
            trigger_category="onboarding",
            team=self.team,
            steps=[
                {"title": "Provision laptop", "assignee_team": "IT", "due_days": 2},
                {"title": "Create accounts", "assignee_team": "IT", "due_days": 3},
            ],
        )
        Rule.objects.create(
            name="Start onboarding on create",
            team=self.team,
            trigger="ticket.created",
            conditions=normalize_conditions([{"field": "category", "op": "equals", "value": "onboarding"}]),
            actions=normalize_actions([{"type": "start_workflow", "template_id": str(self.template.id)}]),
            priority=1,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_ticket_create_starts_workflow_and_steps_advance(self):
        ticket = create_ticket_with_reporter(
            self.owner, self.team, issue_type="New hire", category="onboarding",
        )
        wf = Workflow.objects.filter(ticket=ticket).first()
        self.assertIsNotNone(wf)
        self.assertTrue(RuleExecutionLog.objects.filter(trigger="ticket.created", status="success").exists())

        active = WorkflowStep.objects.filter(workflow=wf, status="active").first()
        self.assertIsNotNone(active)
        self.assertEqual(active.title, "Provision laptop")

        claim_resp = self.client.post(f"/api/workflows/{wf.id}/steps/{active.id}/claim/")
        self.assertEqual(claim_resp.status_code, 200)
        complete_resp = self.client.post(f"/api/workflows/{wf.id}/steps/{active.id}/complete/")
        self.assertEqual(complete_resp.status_code, 200)

        next_step = WorkflowStep.objects.filter(workflow=wf, status="active").first()
        self.assertIsNotNone(next_step)
        self.assertEqual(next_step.title, "Create accounts")
