"""Tests for delegated workspace admin permissions."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from automation.models import Rule
from automation.validation import normalize_actions, normalize_conditions
from base.models import Plan, Subscription, Team, TeamWorkspaceAdmin, UserPreferences
from workflows.models import WorkflowTemplate

User = get_user_model()


def _ensure_active_subscription(user, *, max_members=20):
    """Invite endpoints enforce plan member limits on the team owner."""
    plan, _ = Plan.objects.get_or_create(
        slug="test-workspace-admin",
        defaults={
            "name": "Test Workspace Admin",
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


class WorkspaceAdminPermissionsTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="wowner", email="wowner@example.com", password="pw")
        self.admin = User.objects.create_user(username="wadmin", email="wadmin@example.com", password="pw")
        self.member = User.objects.create_user(username="wmember", email="wmember@example.com", password="pw")
        self.team = Team.objects.create(name="Admin Co", owner=self.owner)
        _ensure_active_subscription(self.owner)
        self.team.members.add(self.owner, self.admin, self.member)
        TeamWorkspaceAdmin.objects.create(
            team=self.team,
            user=self.admin,
            granted_by=self.owner,
            can_manage_playbooks=True,
            can_manage_members=True,
        )
        _set_active_team(self.admin, self.team)
        _set_active_team(self.member, self.team)
        self.client = APIClient()

    def test_owner_can_grant_workspace_admin(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/workspace-admins/grant/",
            {
                "user_id": str(self.member.id),
                "permissions": {"manage_playbooks": True, "manage_members": True},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(TeamWorkspaceAdmin.objects.filter(team=self.team, user=self.member).exists())

    def test_admin_cannot_grant_workspace_admin(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/workspace-admins/grant/",
            {"user_id": str(self.member.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_workspace_admin_can_create_template(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/workflows/templates/manage/",
            {"name": "IT playbook", "steps": [{"title": "Step 1"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(WorkflowTemplate.objects.filter(name="IT playbook", team=self.team).exists())

    def test_workspace_admin_can_create_rule(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/automation/rules/",
            {
                "name": "Admin rule",
                "trigger": "ticket.created",
                "conditions": normalize_conditions([{"field": "category", "op": "equals", "value": "wifi"}]),
                "actions": normalize_actions([{"type": "assign_ticket"}]),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Rule.objects.filter(name="Admin rule", team=self.team).exists())

    def test_member_cannot_create_template(self):
        self.client.force_authenticate(self.member)
        resp = self.client.post(
            "/api/workflows/templates/manage/",
            {"name": "Nope", "steps": [{"title": "Step 1"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_workspace_admin_can_invite_member(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/invite/",
            {"email": "newhire@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_member_cannot_invite(self):
        self.client.force_authenticate(self.member)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/invite/",
            {"email": "blocked@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_owner_can_revoke_workspace_admin(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            f"/api/teams/{self.team.id}/workspace-admins/revoke/",
            {"user_id": str(self.admin.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TeamWorkspaceAdmin.objects.filter(team=self.team, user=self.admin).exists())

    def test_team_list_includes_admin_flags(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/teams/")
        self.assertEqual(resp.status_code, 200)
        team = next(item for item in resp.data if item["id"] == str(self.team.id))
        self.assertTrue(team["is_workspace_admin"])
        self.assertTrue(team["can_manage_members"])
        self.assertFalse(team["is_owner"])
