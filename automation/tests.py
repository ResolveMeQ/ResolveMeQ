from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automation.models import Rule, RuleExecutionLog
from automation.validation import normalize_actions, normalize_conditions
from base.models import Team, UserPreferences
from tickets.services import create_ticket_with_reporter
from workflows.models import Workflow, WorkflowTemplate

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class AutomationRuleEngineTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="rule1", email="rule1@example.com", password="pw")
        self.team = Team.objects.create(name="Rule Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        WorkflowTemplate.objects.create(
            name="Employee onboarding",
            trigger_category="onboarding",
            team=None,
            steps=[{"title": "Step A", "description": "", "assignee_team": "IT"}],
        )
        Rule.objects.create(
            name="Onboarding auto-start",
            team=None,
            trigger="ticket.created",
            conditions=normalize_conditions([{"field": "category", "op": "equals", "value": "onboarding"}]),
            actions=normalize_actions([{"type": "start_workflow", "template_trigger_category": "onboarding"}]),
            priority=10,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_ticket_created_fires_start_workflow_rule(self):
        ticket = create_ticket_with_reporter(
            self.owner, self.team, issue_type="New hire", category="onboarding",
        )
        self.assertTrue(Workflow.objects.filter(ticket=ticket).exists())
        self.assertTrue(
            RuleExecutionLog.objects.filter(trigger="ticket.created", status="success").exists()
        )

    def test_non_matching_category_skips_rule(self):
        ticket = create_ticket_with_reporter(
            self.owner, self.team, issue_type="Wifi", category="wifi",
        )
        self.assertFalse(Workflow.objects.filter(ticket=ticket).exists())

    def test_dry_run_does_not_start_workflow(self):
        from tickets.models import Ticket

        rule = Rule.objects.get(name="Onboarding auto-start")
        ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="New hire",
            category="onboarding",
            status="new",
        )
        before = Workflow.objects.count()
        resp = self.client.post(
            f"/api/automation/rules/{rule.id}/dry-run/",
            {"ticket_id": ticket.ticket_id},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Workflow.objects.count(), before)
        self.assertTrue(any(l["status"] == "dry_run" for l in resp.data["logs"]))

    def test_owner_can_list_rules(self):
        resp = self.client.get("/api/automation/rules/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["can_manage"])
        self.assertGreaterEqual(len(resp.data["rules"]), 1)

    def test_owner_can_update_rule_trigger_and_actions(self):
        rule = Rule.objects.create(
            name="Escalation notify",
            team=self.team,
            trigger="ticket.escalated",
            conditions=[],
            actions=normalize_actions([{"type": "notify_teams"}]),
            priority=50,
        )
        resp = self.client.patch(
            f"/api/automation/rules/{rule.id}/",
            {
                "trigger": "workflow.step.completed",
                "actions": [{"type": "notify_slack", "channel_id": "C123"}],
                "priority": 20,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        rule.refresh_from_db()
        self.assertEqual(rule.trigger, "workflow.step.completed")
        self.assertEqual(rule.actions[0]["type"], "notify_slack")
        self.assertEqual(rule.actions[0]["channel_id"], "C123")
        self.assertEqual(rule.priority, 20)
