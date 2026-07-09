import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automation.hooks import on_ticket_escalated, on_ticket_resolved
from base.models import Team, UserPreferences
from integrations.connectors.jira import normalize_site_url, transition_issue
from integrations.jira_sync import (
    maybe_sync_ticket_escalated_to_jira,
    maybe_sync_ticket_resolved_to_jira,
)
from integrations.models import JiraInstallation
from tickets.models import ExternalReference, Ticket

User = get_user_model()


def _set_active_team(user, team):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    prefs.active_team = team
    prefs.save()


def _mock_json_response(status_code=200, payload=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    if text is not None:
        resp.text = text
    elif payload is not None:
        resp.text = json.dumps(payload)
    else:
        resp.text = ""
    if payload is not None:
        resp.json.return_value = payload
    return resp


class JiraConnectorTest(TestCase):
    def test_normalize_site_url(self):
        self.assertEqual(
            normalize_site_url("acme.atlassian.net"),
            "https://acme.atlassian.net",
        )
        self.assertEqual(
            normalize_site_url("https://acme.atlassian.net/"),
            "https://acme.atlassian.net",
        )

    @patch("integrations.connectors.jira.http_post_json")
    @patch("integrations.connectors.jira.http_get_json")
    def test_transition_issue_finds_transition_by_name(self, mock_get, mock_post):
        mock_get.return_value = _mock_json_response(
            200,
            {"transitions": [{"id": "31", "name": "Done"}, {"id": "21", "name": "In Progress"}]},
        )
        mock_post.return_value = _mock_json_response(204)
        owner = User.objects.create_user(username="jtr", email="jtr@example.com", password="pw")
        team = Team.objects.create(name="Jira Tr", owner=owner)
        inst = JiraInstallation.objects.create(
            resolvemeq_team=team,
            site_url="https://acme.atlassian.net",
            user_email="svc@example.com",
            api_token="token",
            resolve_transition="Done",
            is_active=True,
            installed_by=owner,
        )
        self.assertTrue(transition_issue(inst, "SUP-42", "Done"))
        mock_post.assert_called_once()


class JiraSyncTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="jira1", email="jira1@example.com", password="pw")
        self.team = Team.objects.create(name="Jira Co", owner=self.owner)
        self.team.members.add(self.owner)
        self.installation = JiraInstallation.objects.create(
            resolvemeq_team=self.team,
            site_url="https://acme.atlassian.net",
            user_email="svc@example.com",
            api_token="secret-token",
            project_key="SUP",
            is_active=True,
            installed_by=self.owner,
        )
        self.ticket = Ticket.objects.create(
            user=self.owner,
            team=self.team,
            issue_type="VPN broken",
            category="vpn",
            status="escalated",
            description="Cannot connect",
        )

    @patch("integrations.connectors.jira.http_post_json")
    def test_escalate_creates_issue_and_reference(self, mock_post):
        mock_post.return_value = _mock_json_response(201, {"key": "SUP-101"})
        maybe_sync_ticket_escalated_to_jira(self.ticket)
        ref = ExternalReference.objects.get(ticket=self.ticket, system="jira")
        self.assertEqual(ref.external_id, "SUP-101")
        self.assertIn("SUP-101", ref.external_url)

    @patch("integrations.connectors.jira.http_post_json")
    def test_escalate_skips_when_reference_exists(self, mock_post):
        ExternalReference.objects.create(
            ticket=self.ticket,
            system="jira",
            external_id="SUP-99",
            external_url="https://acme.atlassian.net/browse/SUP-99",
        )
        maybe_sync_ticket_escalated_to_jira(self.ticket)
        mock_post.assert_not_called()

    @patch("integrations.connectors.jira.http_post_json")
    @patch("integrations.connectors.jira.http_get_json")
    def test_resolve_transitions_linked_issue(self, mock_get, mock_post):
        ExternalReference.objects.create(
            ticket=self.ticket,
            system="jira",
            external_id="SUP-55",
            external_url="https://acme.atlassian.net/browse/SUP-55",
        )
        mock_get.return_value = _mock_json_response(
            200,
            {"transitions": [{"id": "31", "name": "Done"}]},
        )
        mock_post.return_value = _mock_json_response(204)
        maybe_sync_ticket_resolved_to_jira(self.ticket)
        ref = ExternalReference.objects.get(pk=self.ticket.external_references.first().pk)
        self.assertEqual(ref.metadata.get("last_sync"), "resolved")

    @patch("integrations.connectors.jira.http_post_json")
    def test_hook_on_escalated_creates_reference(self, mock_post):
        mock_post.return_value = _mock_json_response(201, {"key": "SUP-200"})
        on_ticket_escalated(self.ticket)
        self.assertTrue(
            ExternalReference.objects.filter(ticket=self.ticket, system="jira").exists()
        )


class JiraApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="jira2", email="jira2@example.com", password="pw")
        self.team = Team.objects.create(name="Jira API Co", owner=self.owner)
        self.team.members.add(self.owner)
        _set_active_team(self.owner, self.team)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_status_not_connected(self):
        resp = self.client.get("/api/integrations/jira/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["connected"])

    def test_configure_and_disconnect(self):
        resp = self.client.post(
            "/api/integrations/jira/configure/",
            {
                "team_id": str(self.team.id),
                "site_url": "acme.atlassian.net",
                "user_email": "svc@example.com",
                "api_token": "tok123",
                "project_key": "sup",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["installation"]["has_token"])
        self.assertEqual(resp.data["installation"]["project_key"], "SUP")

        status = self.client.get("/api/integrations/jira/status/")
        self.assertTrue(status.data["connected"])

        disc = self.client.post(
            "/api/integrations/jira/disconnect/",
            {"team_id": str(self.team.id)},
            format="json",
        )
        self.assertTrue(disc.data["disconnected"])
