from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automation.hooks import on_ticket_created, on_ticket_resolved
from base.models import Team, UserPreferences
from monitoring.models import ComplianceAuditEvent
from tickets.models import Ticket

User = get_user_model()


class ComplianceAuditTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner1",
            email="owner@example.com",
            password="pass12345",
        )
        self.member = User.objects.create_user(
            username="member1",
            email="member@example.com",
            password="pass12345",
        )
        self.team = Team.objects.create(name="Audit Team", owner=self.owner, is_active=True)
        self.team.members.add(self.owner, self.member)
        UserPreferences.objects.get_or_create(user=self.owner, defaults={"active_team": self.team})
        prefs, _ = UserPreferences.objects.get_or_create(user=self.member)
        prefs.active_team = self.team
        prefs.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_ticket_hooks_create_audit_events(self):
        ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="VPN issue",
            category="network",
            status="open",
        )
        on_ticket_created(ticket)
        on_ticket_resolved(ticket, actor=self.owner)
        types = set(ComplianceAuditEvent.objects.values_list("event_type", flat=True))
        self.assertIn("ticket.created", types)
        self.assertIn("ticket.resolved", types)

    def test_owner_can_list_audit_events(self):
        ComplianceAuditEvent.objects.create(
            team=self.team,
            actor=self.owner,
            actor_email=self.owner.email,
            event_type="ticket.created",
            resource_type="ticket",
            resource_id="42",
            summary="Ticket #42 created",
        )
        resp = self.client.get("/api/audit/events/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 1)
        self.assertEqual(resp.data["events"][0]["event_type"], "ticket.created")

    def test_member_cannot_list_audit_events(self):
        self.client.force_authenticate(user=self.member)
        resp = self.client.get("/api/audit/events/")
        self.assertEqual(resp.status_code, 403)

    def test_export_csv_records_export_event(self):
        ComplianceAuditEvent.objects.create(
            team=self.team,
            actor=self.owner,
            actor_email=self.owner.email,
            event_type="ticket.created",
            summary="Seed event",
        )
        resp = self.client.get("/api/audit/export/", {"export_format": "csv"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertTrue(
            ComplianceAuditEvent.objects.filter(event_type="audit.exported").exists()
        )

    def test_audit_events_are_immutable(self):
        event = ComplianceAuditEvent.objects.create(
            team=self.team,
            event_type="ticket.created",
            summary="Immutable test",
        )
        event.summary = "Changed"
        with self.assertRaises(ValueError):
            event.save()
