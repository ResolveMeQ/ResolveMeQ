from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automation.engine import run_due_cron_rules
from automation.models import Rule, RuleExecutionLog
from automation.validation import normalize_actions, normalize_conditions, normalize_cron_expression
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
        # A non-matching rule must still leave a trace in real dispatch (not just
        # dry-run), otherwise it's indistinguishable from the trigger never firing.
        self.assertTrue(
            RuleExecutionLog.objects.filter(
                trigger="ticket.created", ticket=ticket, status="skipped"
            ).exists()
        )

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

    def test_billing_support_ticket_fires_escalated_rule(self):
        """create_billing_support_ticket must reach the rules engine like every
        other escalation path (tickets/views.py's escalate_ticket does)."""
        from base.models import SupportContactSubmission
        from tickets.support_enquiry import create_billing_support_ticket

        Rule.objects.create(
            name="Escalated billing notify",
            team=None,
            trigger="ticket.escalated",
            conditions=[],
            actions=normalize_actions([{"type": "set_field", "field": "tags", "value": ["billing_escalated"]}]),
            priority=10,
        )
        submission = SupportContactSubmission.objects.create(
            user=self.owner,
            email=self.owner.email,
            subject="Invoice question",
            message="Why was I charged twice?",
        )
        ticket = create_billing_support_ticket(
            self.owner,
            subject="Invoice question",
            message="Why was I charged twice?",
            page_context="billing",
            submission=submission,
        )
        self.assertTrue(
            RuleExecutionLog.objects.filter(
                trigger="ticket.escalated", ticket=ticket, status="success"
            ).exists()
        )

    def test_owner_can_list_rules(self):
        resp = self.client.get("/api/automation/rules/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["can_manage"])
        self.assertGreaterEqual(len(resp.data["rules"]), 1)

    def test_metadata_lists_all_triggers_and_condition_fields(self):
        resp = self.client.get("/api/automation/metadata/")
        self.assertEqual(resp.status_code, 200)
        trigger_values = [t["value"] for t in resp.data["triggers"]]
        self.assertIn("schedule.cron", trigger_values)
        field_values = {f["value"] for f in resp.data["condition_fields"]}
        self.assertEqual(field_values, {"category", "status", "escalation_priority", "reported_platform"})
        status_field = next(f for f in resp.data["condition_fields"] if f["value"] == "status")
        self.assertIn({"value": "in_progress", "label": "In Progress"}, status_field["choices"])

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


class CronRuleTest(TestCase):
    """schedule.cron trigger: Celery Beat ticks run_due_cron_rules every minute
    (resolvemeq/settings.py CELERY_BEAT_SCHEDULE['automation-cron-rules'])."""

    def setUp(self):
        self.owner = User.objects.create_user(username="cronowner", email="cronowner@example.com", password="pw")
        self.team = Team.objects.create(name="Cron Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_normalize_cron_expression_requires_and_validates(self):
        self.assertEqual(normalize_cron_expression("ticket.created", "anything"), "")
        with self.assertRaises(ValueError):
            normalize_cron_expression("schedule.cron", "")
        with self.assertRaises(ValueError):
            normalize_cron_expression("schedule.cron", "not a cron")
        self.assertEqual(normalize_cron_expression("schedule.cron", "0 9 * * 1"), "0 9 * * 1")

    def test_create_cron_rule_requires_cron_expression(self):
        resp = self.client.post(
            "/api/automation/rules/",
            {
                "name": "Weekly digest",
                "trigger": "schedule.cron",
                "conditions": [],
                "actions": [{"type": "notify_slack", "message": "Weekly check-in"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_cron_rule_with_valid_expression(self):
        resp = self.client.post(
            "/api/automation/rules/",
            {
                "name": "Weekly digest",
                "trigger": "schedule.cron",
                "cron_expression": "0 9 * * 1",
                "conditions": [],
                "actions": [{"type": "notify_slack", "message": "Weekly check-in"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["rule"]["cron_expression"], "0 9 * * 1")

    def test_run_due_cron_rules_fires_and_does_not_double_fire(self):
        rule = Rule.objects.create(
            name="Every minute check",
            team=self.team,
            trigger="schedule.cron",
            cron_expression="* * * * *",
            conditions=[],
            actions=normalize_actions([{"type": "set_field", "field": "status", "value": "escalated"}]),
        )
        now = datetime(2026, 7, 13, 9, 0, tzinfo=dt_timezone.utc)
        fired = run_due_cron_rules(now=now)
        self.assertEqual(fired, [rule.id])
        rule.refresh_from_db()
        self.assertEqual(rule.cron_last_fired_at, now)
        # No ticket in a cron context yet, so a ticket-scoped action correctly no-ops —
        # what this test actually verifies is that the rule fired at all (a log exists).
        log = RuleExecutionLog.objects.get(rule=rule, trigger="schedule.cron")
        self.assertEqual(log.status, "failed")
        self.assertIn("No ticket in context", log.message)

        # Same minute again (e.g. a duplicate/late beat tick) must not double-fire.
        fired_again = run_due_cron_rules(now=now)
        self.assertEqual(fired_again, [])
        self.assertEqual(RuleExecutionLog.objects.filter(rule=rule, trigger="schedule.cron").count(), 1)

    def test_run_due_cron_rules_skips_non_due_expression(self):
        rule = Rule.objects.create(
            name="Monday only",
            team=self.team,
            trigger="schedule.cron",
            cron_expression="0 9 * * 1",
            conditions=[],
            actions=normalize_actions([{"type": "set_field", "field": "status", "value": "escalated"}]),
        )
        # 2026-07-14 is a Tuesday — the rule only fires Mondays at 09:00 UTC.
        now = datetime(2026, 7, 14, 9, 0, tzinfo=dt_timezone.utc)
        fired = run_due_cron_rules(now=now)
        self.assertEqual(fired, [])
        self.assertFalse(RuleExecutionLog.objects.filter(rule=rule).exists())
