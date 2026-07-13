"""Tests for workspace starter automation rules."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from automation.models import Rule
from automation.workspace_starter import seed_starter_rules_for_team
from base.models import Team

User = get_user_model()


class WorkspaceStarterRulesTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="own", email="own@example.com", password="pw")
        self.team = Team.objects.create(name="Starter Co", owner=self.owner)

    def test_seed_creates_editable_team_rules_once(self):
        n = seed_starter_rules_for_team(self.team)
        self.assertEqual(n, 3)
        self.assertEqual(Rule.objects.filter(team=self.team).count(), 3)
        self.assertEqual(seed_starter_rules_for_team(self.team), 0)

    def test_starter_rules_are_team_scoped(self):
        seed_starter_rules_for_team(self.team)
        rule = Rule.objects.filter(team=self.team).first()
        self.assertIsNotNone(rule.team_id)
        self.assertIn("onboarding", rule.name.lower())
