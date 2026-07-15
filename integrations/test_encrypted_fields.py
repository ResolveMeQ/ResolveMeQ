"""
base.encrypted_fields.EncryptedTextField -- applied to OAuth/API credentials in
integrations/models.py (SlackToken.access_token, WebhookEndpoint/Delivery.secret,
Okta/Google/Microsoft365 access+refresh tokens, JiraInstallation.api_token).

Everything here runs against the isolated Django test database, never the real
shared Supabase data -- see encrypt_existing_credentials.py's docstring for why
that distinction matters for this feature.
"""
from cryptography.fernet import Fernet
from django.db import connection
from django.test import TestCase, override_settings

from integrations.models import SlackToken

# Generated fresh for test use only -- has no relationship to any real
# deployment's FIELD_ENCRYPTION_KEY.
TEST_KEY = Fernet.generate_key().decode()


def _raw_access_token(pk):
    """Bypass the model/field entirely to see exactly what's stored in the column."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT access_token FROM integrations_slacktoken WHERE id = %s", [pk])
        return cursor.fetchone()[0]


class EncryptedFieldFlagOffTest(TestCase):
    @override_settings(ENABLE_FIELD_ENCRYPTION=False, FIELD_ENCRYPTION_KEY=TEST_KEY)
    def test_flag_off_stores_plaintext(self):
        token = SlackToken.objects.create(access_token="xoxb-plaintext-token")
        self.assertEqual(_raw_access_token(token.pk), "xoxb-plaintext-token")
        token.refresh_from_db()
        self.assertEqual(token.access_token, "xoxb-plaintext-token")


class EncryptedFieldFlagOnTest(TestCase):
    @override_settings(ENABLE_FIELD_ENCRYPTION=True, FIELD_ENCRYPTION_KEY=TEST_KEY)
    def test_flag_on_encrypts_at_rest_and_decrypts_transparently(self):
        token = SlackToken.objects.create(access_token="xoxb-secret-token")
        raw = _raw_access_token(token.pk)
        self.assertNotEqual(raw, "xoxb-secret-token")  # actually encrypted, not passthrough
        token.refresh_from_db()
        self.assertEqual(token.access_token, "xoxb-secret-token")  # decrypts transparently

    @override_settings(ENABLE_FIELD_ENCRYPTION=True, FIELD_ENCRYPTION_KEY=TEST_KEY)
    def test_preexisting_plaintext_row_still_reads_correctly(self):
        """Row written before the flag was ever on (or before this feature existed) --
        must keep working exactly as before once encryption is turned on."""
        with override_settings(ENABLE_FIELD_ENCRYPTION=False):
            token = SlackToken.objects.create(access_token="xoxb-legacy-plaintext")
        token.refresh_from_db()
        self.assertEqual(token.access_token, "xoxb-legacy-plaintext")

    @override_settings(ENABLE_FIELD_ENCRYPTION=True, FIELD_ENCRYPTION_KEY="")
    def test_flag_on_without_key_behaves_as_plaintext(self):
        token = SlackToken.objects.create(access_token="xoxb-no-key-set")
        self.assertEqual(_raw_access_token(token.pk), "xoxb-no-key-set")


class EncryptExistingCredentialsCommandTest(TestCase):
    def _create_plaintext_token(self):
        with override_settings(ENABLE_FIELD_ENCRYPTION=False):
            return SlackToken.objects.create(access_token="xoxb-backfill-me")

    @override_settings(ENABLE_FIELD_ENCRYPTION=True, FIELD_ENCRYPTION_KEY=TEST_KEY)
    def test_dry_run_does_not_write(self):
        from io import StringIO

        from django.core.management import call_command

        token = self._create_plaintext_token()
        out = StringIO()
        call_command("encrypt_existing_credentials", "--dry-run", stdout=out)
        self.assertIn("would be re-encrypted", out.getvalue())
        self.assertEqual(_raw_access_token(token.pk), "xoxb-backfill-me")

    @override_settings(ENABLE_FIELD_ENCRYPTION=True, FIELD_ENCRYPTION_KEY=TEST_KEY)
    def test_real_run_encrypts_existing_plaintext_row(self):
        from io import StringIO

        from django.core.management import call_command

        token = self._create_plaintext_token()
        call_command("encrypt_existing_credentials", stdout=StringIO())
        self.assertNotEqual(_raw_access_token(token.pk), "xoxb-backfill-me")
        token.refresh_from_db()
        self.assertEqual(token.access_token, "xoxb-backfill-me")

    def test_command_no_ops_when_encryption_not_configured(self):
        from io import StringIO

        from django.core.management import call_command

        token = self._create_plaintext_token()
        out = StringIO()
        call_command("encrypt_existing_credentials", stdout=out)
        self.assertIn("not set", out.getvalue())
        self.assertEqual(_raw_access_token(token.pk), "xoxb-backfill-me")
