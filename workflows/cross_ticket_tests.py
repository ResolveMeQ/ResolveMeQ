from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.models import Ticket
from workflows.models import WorkflowStep, WorkflowTemplate
from workflows.services import _activate_next_steps, start_workflow
from workflows.template_validation import normalize_template_steps

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


CROSS_TICKET_STEPS = [
    {
        "title": "IT provisioning",
        "description": "Create accounts",
        "assignee_team": "IT",
        "assignee_role": "it",
        "step_type": "manual",
        "due_days": 1,
    },
    {
        "title": "Assign hardware",
        "description": "Ship laptop",
        "assignee_team": "IT",
        "assignee_role": "it",
        "step_type": "manual",
        "due_days": 2,
        "spawn_child_ticket": True,
        "child_ticket_category": "provisioning",
    },
    {
        "title": "Facilities access",
        "description": "Badge and desk",
        "assignee_team": "Facilities",
        "assignee_role": "facilities",
        "step_type": "manual",
        "due_days": 2,
        "spawn_child_ticket": True,
        "child_ticket_category": "access",
    },
]


class CrossTicketWorkflowTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="xtx1", email="hire@example.com", password="pw")
        self.team = Team.objects.create(name="Cross Ticket Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.template = WorkflowTemplate.objects.create(
            name="Cross ticket onboarding",
            trigger_category="onboarding",
            team=None,
            steps=normalize_template_steps(CROSS_TICKET_STEPS),
        )
        self.parent = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="New hire Jane",
            category="onboarding",
            status="open",
        )

    def test_active_step_spawns_child_ticket(self):
        workflow = start_workflow(
            template=self.template,
            ticket=self.parent,
            team=self.team,
            started_by=self.owner,
        )
        step0 = workflow.steps.get(order_index=0)
        self.assertEqual(step0.status, "active")
        self.assertIsNone(step0.child_ticket_id)

        step0.status = "done"
        step0.save(update_fields=["status"])
        _activate_next_steps(workflow)

        hw = workflow.steps.get(order_index=1)
        hw.refresh_from_db()
        self.assertEqual(hw.status, "active")
        self.assertIsNotNone(hw.child_ticket_id)
        self.assertEqual(hw.child_ticket.category, "provisioning")
        self.assertIn("workflow_child", hw.child_ticket.tags)

    def test_resolving_child_ticket_completes_workflow_step(self):
        workflow = start_workflow(
            template=self.template,
            ticket=self.parent,
            team=self.team,
            started_by=self.owner,
        )
        step0 = workflow.steps.get(order_index=0)
        step0.status = "done"
        step0.save(update_fields=["status"])
        _activate_next_steps(workflow)

        hw = workflow.steps.get(order_index=1)
        hw.refresh_from_db()
        child = hw.child_ticket
        self.assertIsNotNone(child)
        self.assertEqual(hw.status, "active")

        from automation.hooks import on_ticket_resolved

        child.status = "resolved"
        child.save(update_fields=["status"])
        on_ticket_resolved(child)

        hw.refresh_from_db()
        self.assertEqual(hw.status, "done")
        fac = workflow.steps.get(order_index=2)
        fac.refresh_from_db()
        self.assertEqual(fac.status, "active")
        self.assertIsNotNone(fac.child_ticket_id)

    def test_workflow_api_exposes_child_ticket(self):
        workflow = start_workflow(
            template=self.template,
            ticket=self.parent,
            team=self.team,
            started_by=self.owner,
        )
        step0 = workflow.steps.get(order_index=0)
        step0.status = "done"
        step0.save(update_fields=["status"])
        _activate_next_steps(workflow)

        resp = self.client.get("/api/workflows/")
        wf = next(w for w in resp.data["workflows"] if w["id"] == str(workflow.id))
        hw = wf["steps"][1]
        self.assertIsNotNone(hw["child_ticket"])
        self.assertEqual(hw["child_ticket"]["category"], "provisioning")
