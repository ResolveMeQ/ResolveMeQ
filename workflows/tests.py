from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import InAppNotification, Team, UserPreferences
from tickets.models import Ticket
from tickets.services import create_ticket_with_reporter

from .models import Workflow, WorkflowTemplate
from .scoping import user_can_access_workflow
from .services import maybe_start_workflow_for_ticket, start_workflow

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class WorkflowTriggerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="req1", email="req1@example.com", password="pw")
        self.team = Team.objects.create(name="Trigger Co", owner=self.user)
        self.team.members.add(self.user)
        self.template = WorkflowTemplate.objects.create(
            name="Equipment provisioning",
            trigger_category="provisioning",
            team=None,
            steps=[
                {"title": "Step A", "description": "", "assignee_team": "IT"},
                {"title": "Step B", "description": "", "assignee_team": "IT"},
                {"title": "Step C", "description": "", "assignee_team": "IT"},
            ],
        )

    def test_provisioning_ticket_starts_workflow_with_first_step_active(self):
        ticket = create_ticket_with_reporter(
            self.user, self.team, issue_type="New laptop", category="provisioning",
        )
        workflow = Workflow.objects.get(ticket=ticket)
        steps = list(workflow.steps.order_by("order_index"))
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].status, "active")
        self.assertEqual(steps[1].status, "pending")
        self.assertEqual(steps[2].status, "pending")

    def test_non_matching_category_does_not_start_a_workflow(self):
        ticket = create_ticket_with_reporter(
            self.user, self.team, issue_type="Wifi down", category="wifi",
        )
        self.assertFalse(Workflow.objects.filter(ticket=ticket).exists())

    def test_onboarding_category_matches_onboarding_template_not_provisioning(self):
        onboarding_template = WorkflowTemplate.objects.create(
            name="Onboarding", trigger_category="onboarding", team=None,
            steps=[{"title": "Provision accounts", "description": "", "assignee_team": "IT"}],
        )
        ticket = create_ticket_with_reporter(
            self.user, self.team, issue_type="New hire starting Monday", category="onboarding",
        )
        workflow = Workflow.objects.get(ticket=ticket)
        self.assertEqual(workflow.template_id, onboarding_template.id)

    def test_offboarding_category_matches_offboarding_template(self):
        offboarding_template = WorkflowTemplate.objects.create(
            name="Offboarding", trigger_category="offboarding", team=None,
            steps=[{"title": "Revoke access", "description": "", "assignee_team": "IT"}],
        )
        ticket = create_ticket_with_reporter(
            self.user, self.team, issue_type="Employee leaving", category="offboarding",
        )
        workflow = Workflow.objects.get(ticket=ticket)
        self.assertEqual(workflow.template_id, offboarding_template.id)

    def test_team_specific_template_preferred_over_global(self):
        team_template = WorkflowTemplate.objects.create(
            name="Team-specific provisioning",
            trigger_category="provisioning",
            team=self.team,
            steps=[{"title": "Only step", "description": "", "assignee_team": "IT"}],
        )
        ticket = create_ticket_with_reporter(
            self.user, self.team, issue_type="New laptop", category="provisioning",
        )
        workflow = Workflow.objects.get(ticket=ticket)
        self.assertEqual(workflow.template_id, team_template.id)


class WorkflowStepFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="flow1", email="flow1@example.com", password="pw")
        self.team = Team.objects.create(name="Flow Co", owner=self.user)
        self.team.members.add(self.user)
        _set_active_team(self.user, self.team)
        self.template = WorkflowTemplate.objects.create(
            name="Two-step template",
            trigger_category="",
            team=None,
            steps=[
                {"title": "First", "description": "", "assignee_team": "IT"},
                {"title": "Second", "description": "", "assignee_team": "IT"},
            ],
        )
        self.workflow = start_workflow(template=self.template, team=self.team, started_by=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_claim_is_race_safe(self):
        step = self.workflow.steps.get(order_index=0)
        resp1 = self.client.post(f"/api/workflows/{self.workflow.id}/steps/{step.id}/claim/")
        self.assertEqual(resp1.status_code, 200)
        resp2 = self.client.post(f"/api/workflows/{self.workflow.id}/steps/{step.id}/claim/")
        self.assertEqual(resp2.status_code, 409)

    def test_completing_step_activates_next(self):
        step = self.workflow.steps.get(order_index=0)
        resp = self.client.post(f"/api/workflows/{self.workflow.id}/steps/{step.id}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.workflow.refresh_from_db()
        second = self.workflow.steps.get(order_index=1)
        self.assertEqual(second.status, "active")
        self.assertEqual(self.workflow.status, "in_progress")

    def test_completing_last_step_completes_workflow(self):
        for idx in (0, 1):
            step = self.workflow.steps.get(order_index=idx)
            resp = self.client.post(f"/api/workflows/{self.workflow.id}/steps/{step.id}/complete/")
            self.assertEqual(resp.status_code, 200)
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.status, "completed")

    def test_cannot_complete_a_non_active_step(self):
        second = self.workflow.steps.get(order_index=1)
        resp = self.client.post(f"/api/workflows/{self.workflow.id}/steps/{second.id}/complete/")
        self.assertEqual(resp.status_code, 409)


class WorkflowScopingTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", email="owner1@example.com", password="pw")
        self.team = Team.objects.create(name="Scoped Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.other_owner = User.objects.create_user(username="owner2", email="owner2@example.com", password="pw")
        self.other_team = Team.objects.create(name="Other Co", owner=self.other_owner)
        _set_active_team(self.other_owner, self.other_team)
        self.template = WorkflowTemplate.objects.create(
            name="Scoped template", trigger_category="", team=None,
            steps=[{"title": "Only step", "description": "", "assignee_team": "IT"}],
        )

    def test_team_member_can_access_own_standalone_workflow(self):
        workflow = start_workflow(template=self.template, team=self.team, started_by=self.owner)
        self.assertTrue(user_can_access_workflow(self.owner, workflow))

    def test_other_team_cannot_access_standalone_workflow(self):
        workflow = start_workflow(template=self.template, team=self.team, started_by=self.owner)
        self.assertFalse(user_can_access_workflow(self.other_owner, workflow))

    def test_ticket_linked_workflow_delegates_to_ticket_scoping(self):
        ticket = Ticket.objects.create(
            user=self.owner, team=self.team, issue_type="x", category="other", status="new",
        )
        workflow = start_workflow(template=self.template, ticket=ticket, team=self.team, started_by=self.owner)
        self.assertTrue(user_can_access_workflow(self.owner, workflow))
        self.assertFalse(user_can_access_workflow(self.other_owner, workflow))


class WorkflowNotificationTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="notify1", email="notify1@example.com", password="pw")
        self.member = User.objects.create_user(username="notify2", email="notify2@example.com", password="pw")
        self.team = Team.objects.create(name="Notify Co", owner=self.owner)
        self.team.members.add(self.owner, self.member)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_starting_a_workflow_notifies_team_members(self):
        template = WorkflowTemplate.objects.create(
            name="Onboarding", trigger_category="", team=None,
            steps=[{"title": "Step A", "description": "", "assignee_team": "IT"}],
        )
        start_workflow(template=template, team=self.team, started_by=self.owner)
        self.assertEqual(
            InAppNotification.objects.filter(user__in=[self.owner, self.member], title="New workflow step").count(),
            2,
        )

    def test_completing_a_step_notifies_team_about_the_next_one(self):
        template = WorkflowTemplate.objects.create(
            name="Two-step", trigger_category="", team=None,
            steps=[
                {"title": "First", "description": "", "assignee_team": "IT"},
                {"title": "Second", "description": "", "assignee_team": "IT"},
            ],
        )
        workflow = start_workflow(template=template, team=self.team, started_by=self.owner)
        InAppNotification.objects.all().delete()  # clear the "workflow started" notifications
        first_step = workflow.steps.get(order_index=0)
        self.client.post(f"/api/workflows/{workflow.id}/steps/{first_step.id}/complete/")
        self.assertEqual(
            InAppNotification.objects.filter(user__in=[self.owner, self.member], title="New workflow step").count(),
            2,
        )

    def test_completing_last_step_notifies_ticket_requester_not_team(self):
        requester = User.objects.create_user(username="req9", email="req9@example.com", password="pw")
        ticket = Ticket.objects.create(
            user=requester, team=self.team, issue_type="New laptop", category="provisioning", status="new",
        )
        template = WorkflowTemplate.objects.create(
            name="One-step", trigger_category="", team=None,
            steps=[{"title": "Only step", "description": "", "assignee_team": "IT"}],
        )
        InAppNotification.objects.all().delete()
        workflow = start_workflow(template=template, ticket=ticket, team=self.team, started_by=self.owner)
        InAppNotification.objects.all().delete()  # clear the "workflow started" notifications too
        step = workflow.steps.get(order_index=0)
        self.client.post(f"/api/workflows/{workflow.id}/steps/{step.id}/complete/")
        self.assertTrue(
            InAppNotification.objects.filter(user=requester, title="Your request is complete").exists()
        )
        self.assertFalse(InAppNotification.objects.filter(title="New workflow step").exists())


class WorkflowAutomationTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="auto1", email="auto1@example.com", password="pw")
        self.team = Team.objects.create(name="Auto Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_leading_auto_complete_step_is_skipped_on_start(self):
        template = WorkflowTemplate.objects.create(
            name="Leading auto-complete", trigger_category="", team=None,
            steps=[
                {"title": "Auto step", "description": "", "assignee_team": "IT", "auto_complete": True},
                {"title": "Real step", "description": "", "assignee_team": "IT"},
            ],
        )
        workflow = start_workflow(template=template, team=self.team, started_by=self.owner)
        steps = list(workflow.steps.order_by("order_index"))
        self.assertEqual(steps[0].status, "done")
        self.assertEqual(steps[1].status, "active")

    def test_chain_of_auto_complete_steps_all_resolve_immediately(self):
        template = WorkflowTemplate.objects.create(
            name="Chain", trigger_category="", team=None,
            steps=[
                {"title": "A", "description": "", "assignee_team": "IT", "auto_complete": True},
                {"title": "B", "description": "", "assignee_team": "IT", "auto_complete": True},
                {"title": "C", "description": "", "assignee_team": "IT"},
            ],
        )
        workflow = start_workflow(template=template, team=self.team, started_by=self.owner)
        steps = list(workflow.steps.order_by("order_index"))
        self.assertEqual(steps[0].status, "done")
        self.assertEqual(steps[1].status, "done")
        self.assertEqual(steps[2].status, "active")

    def test_all_auto_complete_steps_completes_the_workflow(self):
        template = WorkflowTemplate.objects.create(
            name="All auto", trigger_category="", team=None,
            steps=[
                {"title": "A", "description": "", "assignee_team": "IT", "auto_complete": True},
                {"title": "B", "description": "", "assignee_team": "IT", "auto_complete": True},
            ],
        )
        workflow = start_workflow(template=template, team=self.team, started_by=self.owner)
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, "completed")

    def test_auto_assign_started_by_sets_claimed_by_without_a_claim_call(self):
        template = WorkflowTemplate.objects.create(
            name="Auto assign", trigger_category="", team=None,
            steps=[{"title": "Assigned step", "description": "", "assignee_team": "IT", "auto_assign": "started_by"}],
        )
        workflow = start_workflow(template=template, team=self.team, started_by=self.owner)
        step = workflow.steps.get(order_index=0)
        self.assertEqual(step.status, "active")
        self.assertEqual(step.claimed_by_id, self.owner.id)

    def test_auto_assign_ticket_reporter(self):
        requester = User.objects.create_user(username="auto2", email="auto2@example.com", password="pw")
        ticket = Ticket.objects.create(
            user=requester, team=self.team, issue_type="x", category="other", status="new",
        )
        template = WorkflowTemplate.objects.create(
            name="Reporter assign", trigger_category="", team=None,
            steps=[{"title": "Step", "description": "", "assignee_team": "IT", "auto_assign": "ticket_reporter"}],
        )
        workflow = start_workflow(template=template, ticket=ticket, team=self.team, started_by=self.owner)
        step = workflow.steps.get(order_index=0)
        self.assertEqual(step.claimed_by_id, requester.id)
