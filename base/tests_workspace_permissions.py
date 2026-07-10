"""Tests for Phase 2 scoped workspace delegation permissions."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from automation.models import Rule
from automation.validation import normalize_actions, normalize_conditions
from base.models import Plan, Subscription, Team, TeamWorkspaceAdmin, UserPreferences
from base.team_permissions import upsert_delegation
from workflows.models import WorkflowTemplate

User = get_user_model()


def _ensure_active_subscription(user, *, max_members=20):
    plan, _ = Plan.objects.get_or_create(
        slug="test-workspace-perms",
        defaults={
            "name": "Test Workspace Perms",
            "max_teams": 10,
            "max_members": max_members,
            "price_monthly": Decimal("0"),
            "price_yearly": Decimal("0"),
        },
    )
    if plan.max_members < max_members:
        plan.max_members = max_members
        plan.save(update_fields=["max_members"])
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": Subscription.Status.TRIAL,
            "trial_ends_at": timezone.now() + timedelta(days=14),
        },
    )


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


class ScopedWorkspacePermissionsTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="sowner", email="sowner@example.com", password="pw")
        self.it_lead = User.objects.create_user(username="itlead", email="itlead@example.com", password="pw")
        self.hr_lead = User.objects.create_user(username="hrlead", email="hrlead@example.com", password="pw")
        self.team = Team.objects.create(name="Scoped Co", owner=self.owner)
        _ensure_active_subscription(self.owner)
        self.team.members.add(self.owner, self.it_lead, self.hr_lead)
        upsert_delegation(
            team=self.team,
            user=self.it_lead,
            granted_by=self.owner,
            permissions_raw={
                "manage_playbooks": True,
                "manage_members": False,
                "manage_integrations": True,
                "manage_webhooks": False,
                "manage_partner_api": False,
                "view_audit_log": False,
            },
        )
        upsert_delegation(
            team=self.team,
            user=self.hr_lead,
            granted_by=self.owner,
            permissions_raw={
                "manage_playbooks": False,
                "manage_members": True,
                "manage_integrations": False,
                "manage_webhooks": False,
                "manage_partner_api": False,
                "view_audit_log": True,
            },
        )
        _set_active_team(self.it_lead, self.team)
        _set_active_team(self.hr_lead, self.team)
        self.client = APIClient()

    def test_it_lead_can_create_template_but_hr_cannot(self):
        self.client.force_authenticate(self.it_lead)
        resp = self.client.post(
            "/api/workflows/templates/manage/",
            {"name": "IT playbook", "steps": [{"title": "Step 1"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        self.client.force_authenticate(self.hr_lead)
        resp = self.client.post(
            "/api/workflows/templates/manage/",
            {"name": "HR playbook", "steps": [{"title": "Step 1"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_hr_lead_can_invite_but_it_lead_cannot(self):
        self.client.force_authenticate(self.hr_lead)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/invite/",
            {"email": "newperson@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        self.client.force_authenticate(self.it_lead)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/invite/",
            {"email": "blocked@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_owner_can_update_permissions_scopes(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/workspace-admins/grant/",
            {
                "user_id": str(self.it_lead.id),
                "permissions": {
                    "manage_playbooks": True,
                    "manage_members": True,
                    "manage_integrations": False,
                    "manage_webhooks": True,
                    "manage_partner_api": False,
                    "view_audit_log": False,
                },
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        grant = TeamWorkspaceAdmin.objects.get(team=self.team, user=self.it_lead)
        self.assertTrue(grant.can_manage_members)
        self.assertTrue(grant.can_manage_webhooks)
        self.assertFalse(grant.can_manage_integrations)

    def test_permission_scopes_metadata(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.get("/api/teams/permission-scopes/")
        self.assertEqual(resp.status_code, 200)
        keys = {item["key"] for item in resp.data["scopes"]}
        self.assertIn("manage_playbooks", keys)
        self.assertIn("view_audit_log", keys)

    def test_team_payload_includes_workspace_permissions(self):
        self.client.force_authenticate(self.it_lead)
        resp = self.client.get("/api/teams/")
        team = next(item for item in resp.data if item["id"] == str(self.team.id))
        self.assertTrue(team["workspace_permissions"]["manage_playbooks"])
        self.assertFalse(team["workspace_permissions"]["manage_members"])
        self.assertTrue(team["workspace_permissions"]["manage_integrations"])

    def test_hr_can_list_rules_read_only(self):
        Rule.objects.create(
            name="Global",
            team=None,
            trigger="ticket.created",
            conditions=normalize_conditions([]),
            actions=normalize_actions([{"type": "assign_ticket"}]),
        )
        self.client.force_authenticate(self.hr_lead)
        resp = self.client.get("/api/automation/rules/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["can_manage"])

    def test_clearing_all_permissions_revokes_grant(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/workspace-admins/grant/",
            {
                "user_id": str(self.hr_lead.id),
                "permissions": {
                    "manage_playbooks": False,
                    "manage_members": False,
                    "manage_integrations": False,
                    "manage_webhooks": False,
                    "manage_partner_api": False,
                    "view_audit_log": False,
                },
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TeamWorkspaceAdmin.objects.filter(team=self.team, user=self.hr_lead).exists())
