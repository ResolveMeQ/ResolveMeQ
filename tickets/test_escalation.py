"""
Tests for the escalation UX rework: priority/SLA derivation, unified notification copy,
claim flow (race-safety + customer notification), queue ordering, and the rollback
whitelist gaps fixed alongside it.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .escalation_copy import compute_sla_due_at, derive_escalation_priority
from .models import ActionHistory, Ticket
from .rollback import RollbackManager
from .sla_settings import escalation_sla_hours

User = get_user_model()


class DeriveEscalationPriorityTest(TestCase):
    def test_explicit_priority_wins(self):
        self.assertEqual(derive_escalation_priority({"priority": "critical", "severity": "low"}), "critical")

    def test_severity_used_when_no_explicit_priority(self):
        self.assertEqual(derive_escalation_priority({"severity": "high"}), "high")

    def test_request_reason_key_mapping(self):
        self.assertEqual(derive_escalation_priority({"request_reason_key": "urgent_blocked"}), "high")
        self.assertEqual(derive_escalation_priority({"request_reason_key": "security_access"}), "high")
        self.assertEqual(derive_escalation_priority({"request_reason_key": "talk_to_human"}), "medium")
        self.assertEqual(derive_escalation_priority({"request_reason_key": "billing_account"}), "medium")

    def test_default_medium_with_no_signal(self):
        self.assertEqual(derive_escalation_priority({}), "medium")
        self.assertEqual(derive_escalation_priority(None), "medium")


class SlaSettingsTest(TestCase):
    def test_default_hours_per_priority(self):
        self.assertEqual(escalation_sla_hours("critical"), 2)
        self.assertEqual(escalation_sla_hours("high"), 8)
        self.assertEqual(escalation_sla_hours("medium"), 24)
        self.assertEqual(escalation_sla_hours("low"), 48)

    @override_settings(ESCALATION_SLA_HOURS={"critical": 1})
    def test_settings_override(self):
        self.assertEqual(escalation_sla_hours("critical"), 1)
        self.assertEqual(escalation_sla_hours("high"), 8)  # unaffected tiers keep defaults

    def test_compute_sla_due_at(self):
        now = timezone.now()
        due = compute_sla_due_at(now, "high")
        self.assertAlmostEqual((due - now).total_seconds(), 8 * 3600, delta=1)
        self.assertIsNone(compute_sla_due_at(None, "high"))


class EscalateTicketViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="requester", email="req@example.com", password="testpass123")
        self.client.force_authenticate(user=self.user)
        self.ticket = Ticket.objects.create(
            user=self.user, issue_type="vpn (high)", status="in_progress",
            description="Can't connect", category="vpn",
        )

    def test_escalate_sets_priority_and_sla(self):
        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/escalate/", {"reason": "urgent_blocked"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.escalation_priority, "high")
        self.assertIsNotNone(self.ticket.sla_due_at)
        self.assertEqual(resp.data["eta"]["priority"], "high")

    def test_escalate_is_idempotent(self):
        self.client.post(f"/api/tickets/{self.ticket.ticket_id}/escalate/", {"reason": "urgent_blocked"}, format="json")
        self.ticket.refresh_from_db()
        first_sla = self.ticket.sla_due_at

        resp = self.client.post(f"/api/tickets/{self.ticket.ticket_id}/escalate/", {"reason": "other"}, format="json")
        self.assertEqual(resp.data["message"], "Ticket is already in review.")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.sla_due_at, first_sla)  # not overwritten by the second (low-priority) call

    @patch("tickets.user_email_notify.dispatch_ticket_status_emails")
    def test_escalate_dispatches_customer_email(self, mock_email):
        self.client.post(f"/api/tickets/{self.ticket.ticket_id}/escalate/", {"reason": "talk_to_human"}, format="json")
        mock_email.assert_called_once()
        args, kwargs = mock_email.call_args
        self.assertEqual(args[0], self.ticket)
        self.assertEqual(args[2], "escalated")
        self.assertIn("escalation_msg", kwargs)
        self.assertEqual(kwargs["escalation_msg"]["priority"], "medium")

    @patch("integrations.views.notify_escalation")
    def test_escalate_passes_real_reason_and_priority_to_slack(self, mock_notify):
        self.client.post(f"/api/tickets/{self.ticket.ticket_id}/escalate/", {"reason": "security_access"}, format="json")
        mock_notify.assert_called_once()
        _, _, params = mock_notify.call_args[0]
        # Regression test: these keys used to be missing on the manual escalation path,
        # so notify_escalation's Slack message always fell back to generic text.
        self.assertEqual(params["priority"], "high")
        self.assertIn("escalation_reason", params)
        self.assertNotEqual(params["escalation_reason"], "")


class AssignTicketClaimTest(TestCase):
    def setUp(self):
        from base.models import Team, UserPreferences

        self.client = APIClient()
        self.requester = User.objects.create_user(username="requester2", email="req2@example.com", password="testpass123")
        self.agent = User.objects.create_user(username="agent1", email="agent1@example.com", password="testpass123")
        self.other_agent = User.objects.create_user(username="agent2", email="agent2@example.com", password="testpass123")

        # Claiming is a team-internal action (tickets/scoping.py): the agent needs an
        # active team that owns the ticket, same as any other teammate would in real use.
        self.team = Team.objects.create(name="Support Team", owner=self.requester)
        self.team.members.add(self.agent, self.other_agent)
        for u in (self.agent, self.other_agent):
            prefs, _ = UserPreferences.objects.get_or_create(user=u)
            prefs.active_team = self.team
            prefs.save()

        self.client.force_authenticate(user=self.agent)
        self.ticket = Ticket.objects.create(
            user=self.requester, team=self.team, issue_type="server (critical)", status="escalated",
            description="Server down", category="server",
        )
        self.ticket.escalated_at = timezone.now()
        self.ticket.save()

    @patch("tickets.views.dispatch_ticket_claimed_email")
    def test_first_claim_sets_fields_and_notifies_once(self, mock_email):
        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.agent.id)}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.claimed_at)
        self.assertEqual(self.ticket.assigned_to_id, self.agent.id)
        self.assertTrue(ActionHistory.objects.filter(ticket=self.ticket, action_type="CLAIM").exists())
        mock_email.assert_called_once_with(self.ticket, self.agent)

    @patch("tickets.views.dispatch_ticket_claimed_email")
    def test_reassignment_after_claim_does_not_renotify(self, mock_email):
        self.client.post(f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.agent.id)}, format="json")
        mock_email.reset_mock()

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.other_agent.id)}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        mock_email.assert_not_called()
        self.assertEqual(ActionHistory.objects.filter(ticket=self.ticket, action_type="CLAIM").count(), 1)

    @patch("tickets.views.dispatch_ticket_claimed_email")
    def test_self_assignment_by_requester_does_not_notify(self, mock_email):
        self.client.force_authenticate(user=self.requester)
        self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.requester.id)}, format="json",
        )
        mock_email.assert_not_called()
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.claimed_at)

    @patch("tickets.views.dispatch_ticket_claimed_email")
    def test_assigning_non_escalated_ticket_does_not_set_claimed_at(self, mock_email):
        self.ticket.status = "in_progress"
        self.ticket.save()
        self.client.post(f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.agent.id)}, format="json")
        mock_email.assert_not_called()
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.claimed_at)

    def test_claim_race_second_call_loses(self):
        """Simulates the race by calling the same conditional UPDATE twice in sequence."""
        first = Ticket.objects.filter(pk=self.ticket.pk, claimed_at__isnull=True).update(
            claimed_at=timezone.now(), assigned_to=self.agent,
        )
        second = Ticket.objects.filter(pk=self.ticket.pk, claimed_at__isnull=True).update(
            claimed_at=timezone.now(), assigned_to=self.other_agent,
        )
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to_id, self.agent.id)

    def test_sequential_reassignment_is_allowed_not_treated_as_conflict(self):
        """
        A *genuine* race (two simultaneous claims) is covered at the DB layer by
        test_claim_race_second_call_loses -- sequential requests can't reproduce true
        concurrency since the first call's UPDATE always commits before the second
        starts. By design, a second assign call after a claim is a normal reassignment
        (see assign_ticket's is_claim_attempt check), not a conflict.
        """
        self.client.post(f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.agent.id)}, format="json")
        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/assign/", {"agent_id": str(self.other_agent.id)}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Ticket assigned to", resp.data["message"])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to_id, self.other_agent.id)
        # claimed_at is sticky -- sticky to whoever claimed it first, not bumped by reassignment.
        self.assertIsNotNone(self.ticket.claimed_at)


class EscalationQueueOrderingTest(TestCase):
    def setUp(self):
        from base.models import Team

        self.client = APIClient()
        self.user = User.objects.create_user(username="queueuser", email="queue@example.com", password="testpass123")
        # Escalation queue requires platform agent or team owner (see base.escalation_access).
        Team.objects.create(name="Queue Team", owner=self.user)
        self.client.force_authenticate(user=self.user)

        def make(priority, minutes_ago):
            t = Ticket.objects.create(
                user=self.user, issue_type="x", status="escalated", description="d", category="other",
            )
            t.escalation_priority = priority
            t.escalated_at = timezone.now() - timezone.timedelta(minutes=minutes_ago)
            t.save()
            return t

        self.low_old = make("low", 100)
        self.high_new = make("high", 5)
        self.high_old = make("high", 50)
        self.critical = make("critical", 1)

    def test_ordered_by_priority_then_age(self):
        resp = self.client.get("/api/tickets/escalated/")
        self.assertEqual(resp.status_code, 200)
        ids = [t["ticket_id"] for t in resp.data["tickets"]]
        self.assertEqual(
            ids,
            [self.critical.ticket_id, self.high_old.ticket_id, self.high_new.ticket_id, self.low_old.ticket_id],
        )


class RollbackWhitelistTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rbuser", email="rb@example.com", password="testpass123")
        self.agent = User.objects.create_user(username="rbagent", email="rbagent@example.com", password="testpass123")
        self.ticket = Ticket.objects.create(
            user=self.user, issue_type="x", status="escalated", description="d", category="other",
        )

    def test_manual_resolve_now_rollback_capable(self):
        self.assertTrue(RollbackManager.can_rollback("MANUAL_RESOLVE"))

    def test_claim_now_rollback_capable(self):
        self.assertTrue(RollbackManager.can_rollback("CLAIM"))

    def test_execute_rollback_claim_restores_state(self):
        self.ticket.assigned_to = self.agent
        self.ticket.claimed_at = timezone.now()
        self.ticket.save()
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type="CLAIM",
            before_state={"assigned_to_id": None, "claimed_at": None},
            after_state={"assigned_to_id": str(self.agent.id), "claimed_at": "now"},
            executed_by="rbagent",
        )
        success = RollbackManager.execute_rollback(action, self.user, "wrong agent")
        self.assertTrue(success)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assigned_to_id)
        self.assertIsNone(self.ticket.claimed_at)
        action.refresh_from_db()
        self.assertTrue(action.rolled_back)
