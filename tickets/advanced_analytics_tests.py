from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.models import Ticket
from tickets.outcome_helpers import log_agent_confidence_snapshot
from workflows.models import WorkflowStep, WorkflowTemplate
from workflows.services import start_workflow

User = get_user_model()


class AdvancedAnalyticsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="adv1", email="adv@test.com", password="x")
        self.team = Team.objects.create(name="Analytics Team", owner=self.user, is_active=True)
        self.team.members.add(self.user)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.user)
        prefs.active_team = self.team
        prefs.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.template = WorkflowTemplate.objects.create(
            name="Onboarding",
            trigger_category="onboarding",
            team=self.team,
            steps=[
                {"title": "Provision accounts", "description": "", "assignee_team": "IT", "due_days": 1},
                {"title": "Assign hardware", "description": "", "assignee_team": "IT", "due_days": 2},
            ],
        )

    def test_deflection_by_category(self):
        Ticket.objects.create(
            user=self.user, team=self.team, issue_type="VPN", category="vpn",
            status="resolved", agent_processed=True, description="x",
        )
        Ticket.objects.create(
            user=self.user, team=self.team, issue_type="WiFi", category="wifi",
            status="escalated", agent_processed=True, description="x", escalated_at=timezone.now(),
        )
        resp = self.client.get("/api/tickets/advanced-analytics/")
        self.assertEqual(resp.status_code, 200)
        cats = {c["category"]: c for c in resp.data["deflection_by_category"]}
        self.assertEqual(cats["vpn"]["deflection_rate_percent"], 100.0)
        self.assertEqual(cats["wifi"]["deflection_rate_percent"], 0.0)

    def test_confidence_calibration_buckets(self):
        ticket = Ticket.objects.create(
            user=self.user, team=self.team, issue_type="Email", category="email",
            status="resolved", agent_processed=True, description="x",
        )
        log_agent_confidence_snapshot(ticket, "analyze", confidence=0.9, recommended_action="auto_resolve")
        resp = self.client.get("/api/tickets/advanced-analytics/")
        self.assertEqual(resp.status_code, 200)
        buckets = resp.data["confidence_calibration"]
        self.assertTrue(any(b["confidence_bucket"] == "0.8-1.0" for b in buckets))

    def test_workflow_bottlenecks(self):
        ticket = Ticket.objects.create(
            user=self.user, team=self.team, issue_type="Hire", category="onboarding",
            status="open", description="x",
        )
        wf = start_workflow(template=self.template, ticket=ticket, team=self.team, started_by=self.user)
        step = WorkflowStep.objects.filter(workflow=wf, order_index=0).first()
        step.status = "active"
        step.due_at = timezone.now() - timezone.timedelta(hours=2)
        step.save()
        resp = self.client.get("/api/tickets/advanced-analytics/")
        self.assertEqual(resp.status_code, 200)
        bottlenecks = resp.data["workflow_bottlenecks"]
        self.assertTrue(len(bottlenecks) >= 1)
        self.assertGreaterEqual(bottlenecks[0]["overdue_now"], 1)
