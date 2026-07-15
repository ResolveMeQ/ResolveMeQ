from unittest.mock import patch

from django.test import TestCase

from integrations.connectors.google_workspace import (
    run_google_action,
)
from integrations.connectors.google_workspace import (
    deactivate_user as google_deactivate_user,
)
from integrations.connectors.google_workspace import (
    remove_from_group as google_remove_from_group,
)
from integrations.connectors.google_workspace import (
    reset_password as google_reset_password,
)
from integrations.connectors.google_workspace import (
    revoke_license as google_revoke_license,
)
from integrations.connectors.microsoft365 import (
    run_microsoft_action,
)
from integrations.connectors.microsoft365 import (
    deactivate_user as microsoft_deactivate_user,
)
from integrations.connectors.microsoft365 import (
    remove_from_group as microsoft_remove_from_group,
)
from integrations.connectors.microsoft365 import (
    reset_password as microsoft_reset_password,
)
from integrations.connectors.microsoft365 import (
    revoke_license as microsoft_revoke_license,
)
from integrations.connectors.okta import (
    deactivate_user as okta_deactivate_user,
)
from integrations.connectors.okta import (
    remove_from_group as okta_remove_from_group,
)
from integrations.connectors.okta import (
    reset_password as okta_reset_password,
)
from integrations.connectors.okta import run_okta_action
from integrations.models import GoogleWorkspaceInstallation, Microsoft365Installation, OktaInstallation


class OktaDirectoryActionTest(TestCase):
    def setUp(self):
        self.inst = OktaInstallation(
            okta_domain="dev-123",
            issuer_url="https://dev-123.okta.com/oauth2/default",
            access_token="token",
        )

    @patch("integrations.connectors.okta.okta_api_post")
    @patch("integrations.connectors.okta.find_user_by_email")
    def test_deactivate_user_calls_lifecycle_endpoint(self, mock_find, mock_post):
        mock_find.return_value = {"id": "00u1"}
        ok, msg, detail = okta_deactivate_user(self.inst, "leaver@example.com")
        self.assertTrue(ok)
        mock_post.assert_called_once_with(self.inst, "/api/v1/users/00u1/lifecycle/deactivate")
        self.assertEqual(detail["user_id"], "00u1")

    @patch("integrations.connectors.okta.okta_api_post")
    @patch("integrations.connectors.okta.find_user_by_email")
    def test_reset_password_sends_email(self, mock_find, mock_post):
        mock_find.return_value = {"id": "00u1"}
        ok, msg, detail = okta_reset_password(self.inst, "user@example.com")
        self.assertTrue(ok)
        mock_post.assert_called_once_with(self.inst, "/api/v1/users/00u1/lifecycle/reset_password?sendEmail=true")

    @patch("integrations.connectors.okta.okta_api_delete")
    @patch("integrations.connectors.okta.find_user_by_email")
    def test_remove_from_group_calls_delete(self, mock_find, mock_delete):
        mock_find.return_value = {"id": "00u1"}
        ok, msg, detail = okta_remove_from_group(self.inst, "user@example.com", "00g1")
        self.assertTrue(ok)
        mock_delete.assert_called_once_with(self.inst, "/api/v1/groups/00g1/users/00u1")

    @patch("integrations.connectors.okta.find_user_by_email")
    def test_deactivate_user_missing_user_fails(self, mock_find):
        mock_find.return_value = None
        ok, msg, detail = okta_deactivate_user(self.inst, "missing@example.com")
        self.assertFalse(ok)

    def test_run_okta_action_rejects_unknown_action(self):
        ok, msg, detail = run_okta_action(self.inst, "delete_everything", email="a@b.com")
        self.assertFalse(ok)


class GoogleDirectoryActionTest(TestCase):
    def setUp(self):
        self.inst = GoogleWorkspaceInstallation(access_token="token")

    @patch("integrations.connectors.google_workspace.google_api_patch")
    @patch("integrations.connectors.google_workspace.find_user_by_email")
    def test_deactivate_user_suspends(self, mock_find, mock_patch):
        mock_find.return_value = {"primaryEmail": "leaver@example.com"}
        ok, msg, detail = google_deactivate_user(self.inst, "leaver@example.com")
        self.assertTrue(ok)
        args, _ = mock_patch.call_args
        self.assertEqual(args[2], {"suspended": True})

    @patch("integrations.connectors.google_workspace.google_api_patch")
    @patch("integrations.connectors.google_workspace.find_user_by_email")
    def test_reset_password_returns_temp_password_in_detail_only(self, mock_find, mock_patch):
        mock_find.return_value = {"primaryEmail": "user@example.com"}
        ok, msg, detail = google_reset_password(self.inst, "user@example.com")
        self.assertTrue(ok)
        self.assertIn("temp_password", detail)
        self.assertTrue(len(detail["temp_password"]) >= 12)

    @patch("integrations.connectors.google_workspace.google_api_delete")
    def test_remove_from_group(self, mock_delete):
        ok, msg, detail = google_remove_from_group(self.inst, "user@example.com", "group@example.com")
        self.assertTrue(ok)
        mock_delete.assert_called_once()

    def test_remove_from_group_requires_group_id(self):
        ok, msg, detail = google_remove_from_group(self.inst, "user@example.com", "")
        self.assertFalse(ok)

    @patch("integrations.connectors.google_workspace.google_api_delete")
    def test_revoke_license(self, mock_delete):
        ok, msg, detail = google_revoke_license(self.inst, "user@example.com", "Google-Apps-For-Business")
        self.assertTrue(ok)
        mock_delete.assert_called_once()

    @patch("integrations.connectors.google_workspace.google_api_patch")
    @patch("integrations.connectors.google_workspace.find_user_by_email")
    def test_run_google_action_dispatches_deactivate(self, mock_find, mock_patch):
        mock_find.return_value = {"primaryEmail": "user@example.com"}
        ok, msg, detail = run_google_action(self.inst, "deactivate_user", email="user@example.com")
        self.assertTrue(ok)


class MicrosoftDirectoryActionTest(TestCase):
    def setUp(self):
        self.inst = Microsoft365Installation(access_token="token", tenant_id="tenant1")

    @patch("integrations.connectors.microsoft365.graph_api_patch")
    @patch("integrations.connectors.microsoft365.find_user_by_email")
    def test_deactivate_user_disables_account(self, mock_find, mock_patch):
        mock_find.return_value = {"id": "u1"}
        ok, msg, detail = microsoft_deactivate_user(self.inst, "leaver@example.com")
        self.assertTrue(ok)
        mock_patch.assert_called_once_with(self.inst, "/users/u1", {"accountEnabled": False})

    @patch("integrations.connectors.microsoft365.graph_api_patch")
    @patch("integrations.connectors.microsoft365.find_user_by_email")
    def test_reset_password_returns_temp_password_in_detail_only(self, mock_find, mock_patch):
        mock_find.return_value = {"id": "u1"}
        ok, msg, detail = microsoft_reset_password(self.inst, "user@example.com")
        self.assertTrue(ok)
        self.assertIn("temp_password", detail)

    @patch("integrations.connectors.microsoft365.graph_api_delete")
    @patch("integrations.connectors.microsoft365.find_user_by_email")
    def test_remove_from_group_uses_ref_delete(self, mock_find, mock_delete):
        mock_find.return_value = {"id": "u1"}
        ok, msg, detail = microsoft_remove_from_group(self.inst, "user@example.com", "g1")
        self.assertTrue(ok)
        mock_delete.assert_called_once_with(self.inst, "/groups/g1/members/u1/$ref")

    @patch("integrations.connectors.microsoft365.graph_api_post")
    @patch("integrations.connectors.microsoft365.find_user_by_email")
    def test_revoke_license_calls_assign_license(self, mock_find, mock_post):
        mock_find.return_value = {"id": "u1"}
        ok, msg, detail = microsoft_revoke_license(self.inst, "user@example.com", "SKU123")
        self.assertTrue(ok)
        mock_post.assert_called_once_with(self.inst, "/users/u1/assignLicense", {"addLicenses": [], "removeLicenses": ["SKU123"]})

    @patch("integrations.connectors.microsoft365.graph_api_patch")
    @patch("integrations.connectors.microsoft365.find_user_by_email")
    def test_run_microsoft_action_dispatches_deactivate(self, mock_find, mock_patch):
        mock_find.return_value = {"id": "u1"}
        ok, msg, detail = run_microsoft_action(self.inst, "deactivate_user", email="user@example.com")
        self.assertTrue(ok)
