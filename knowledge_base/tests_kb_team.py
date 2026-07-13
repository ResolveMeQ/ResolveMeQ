"""KB team scoping for agent search and article permissions."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base.models import Team, UserPreferences
from knowledge_base.models import KnowledgeBaseArticle

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


@override_settings(AGENT_API_KEY="test-agent-key")
class KBAgentTeamScopeTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="kbowner", email="kbowner@example.com", password="pw")
        self.team = Team.objects.create(name="KB Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        KnowledgeBaseArticle.objects.create(
            title="Global VPN guide",
            content="Global baseline VPN steps.",
            tags=["vpn"],
            team=None,
        )
        KnowledgeBaseArticle.objects.create(
            title="Acme VPN policy",
            content="Use Acme split tunnel VPN client only.",
            tags=["vpn", "acme"],
            team=self.team,
        )
        self.client = APIClient()
        self.client.credentials(HTTP_X_AGENT_API_KEY="test-agent-key")

    def test_agent_search_without_team_id_returns_global_only(self):
        resp = self.client.post(
            "/api/knowledge_base/api/search/",
            {"query": "vpn acme", "limit": 10},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        titles = [r["title"] for r in resp.data["results"]]
        self.assertIn("Global VPN guide", titles)
        self.assertNotIn("Acme VPN policy", titles)

    def test_agent_search_with_team_id_includes_workspace_articles(self):
        resp = self.client.post(
            "/api/knowledge_base/api/search/",
            {"query": "vpn acme", "limit": 10, "team_id": str(self.team.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        titles = [r["title"] for r in resp.data["results"]]
        self.assertIn("Acme VPN policy", titles)
        self.assertIn("Global VPN guide", titles)


class KBArticleAuthoringTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="author", email="author@example.com", password="pw")
        self.member = User.objects.create_user(username="member", email="member@example.com", password="pw")
        self.team = Team.objects.create(name="Author Co", owner=self.owner)
        self.team.members.add(self.owner, self.member)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_owner_can_create_workspace_article(self):
        resp = self.client.post(
            "/api/knowledge_base/articles/",
            {
                "title": "Password reset",
                "content": "## Steps\n1. Go to portal",
                "tags": ["password"],
                "is_published": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        article = KnowledgeBaseArticle.objects.get(title="Password reset")
        self.assertEqual(article.team_id, self.team.id)
        self.assertEqual(article.author_id, self.owner.id)

    def test_member_without_permission_cannot_create(self):
        _set_active_team(self.member, self.team)
        client = APIClient()
        client.force_authenticate(self.member)
        resp = client.post(
            "/api/knowledge_base/articles/",
            {"title": "Blocked", "content": "Nope", "tags": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_metadata_reports_can_manage_for_owner(self):
        resp = self.client.get("/api/knowledge_base/metadata/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["can_manage"])
