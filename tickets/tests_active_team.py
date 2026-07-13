"""Tests for automatic active workspace selection."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from tickets.active_team import maybe_auto_select_active_team, set_active_team_if_unset

User = get_user_model()


class ActiveTeamAutoSelectTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="solo",
            email="solo@example.com",
            password="pw",
        )
        self.team = Team.objects.create(name="Solo Co", owner=self.user)
        self.team.members.add(self.user)

    def test_maybe_auto_select_when_single_team_and_no_preference(self):
        prefs = maybe_auto_select_active_team(self.user)
        self.assertEqual(prefs.active_team_id, self.team.id)

    def test_preferences_get_auto_selects_single_team(self):
        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.get("/api/auth/preferences/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.data["active_team"]), str(self.team.id))

    def test_does_not_override_valid_active_team(self):
        prefs, _ = UserPreferences.objects.get_or_create(user=self.user)
        prefs.active_team = self.team
        prefs.save()
        other = Team.objects.create(name="Other", owner=self.user)
        other.members.add(self.user)
        prefs = maybe_auto_select_active_team(self.user)
        self.assertEqual(prefs.active_team_id, self.team.id)

    def test_set_active_team_if_unset_on_invite_accept_pattern(self):
        prefs = set_active_team_if_unset(self.user, self.team)
        self.assertEqual(prefs.active_team_id, self.team.id)
