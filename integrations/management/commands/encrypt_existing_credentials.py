"""
Backfill: re-encrypt credential fields that were written before
ENABLE_FIELD_ENCRYPTION was turned on (or before this feature existed at all).

Never runs automatically (not a data migration) -- deliberately a manual,
one-off command so it can never surprise or block a deploy. Safe to run more
than once: reading an already-encrypted value decrypts it, and re-saving just
re-encrypts the same plaintext with a fresh Fernet token (harmless).

Usage:
    python manage.py encrypt_existing_credentials --dry-run
    python manage.py encrypt_existing_credentials
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.models import (
    GoogleWorkspaceInstallation,
    JiraInstallation,
    Microsoft365Installation,
    OktaInstallation,
    SlackToken,
    WebhookDelivery,
    WebhookEndpoint,
)

logger = logging.getLogger(__name__)

# (model, [encrypted field names])
TARGETS = [
    (SlackToken, ["access_token"]),
    (WebhookEndpoint, ["secret"]),
    (WebhookDelivery, ["secret"]),
    (OktaInstallation, ["access_token", "refresh_token"]),
    (GoogleWorkspaceInstallation, ["access_token", "refresh_token"]),
    (Microsoft365Installation, ["access_token", "refresh_token"]),
    (JiraInstallation, ["api_token"]),
]


class Command(BaseCommand):
    help = "Re-encrypt integration credential fields with the current FIELD_ENCRYPTION_KEY."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report how many rows would be touched per model/field without writing anything.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "ENABLE_FIELD_ENCRYPTION", False) or not getattr(settings, "FIELD_ENCRYPTION_KEY", ""):
            self.stdout.write(self.style.WARNING(
                "ENABLE_FIELD_ENCRYPTION and/or FIELD_ENCRYPTION_KEY are not set -- "
                "nothing would actually be encrypted. Set both, then re-run."
            ))
            return

        dry_run = options["dry_run"]
        total_touched = 0
        total_errors = 0

        for model, fields in TARGETS:
            for field in fields:
                qs = model.objects.exclude(**{field: ""}).exclude(**{f"{field}__isnull": True})
                count = qs.count()
                if count == 0:
                    continue
                label = f"{model.__name__}.{field}"
                if dry_run:
                    self.stdout.write(f"[dry-run] {label}: {count} row(s) would be re-encrypted.")
                    total_touched += count
                    continue

                touched = 0
                for obj in qs.iterator():
                    try:
                        # Attribute access decrypts (or passes through plaintext);
                        # save() re-encrypts on write via EncryptedTextField.
                        setattr(obj, field, getattr(obj, field))
                        obj.save(update_fields=[field])
                        touched += 1
                    except Exception as exc:
                        total_errors += 1
                        logger.warning("Could not re-encrypt %s pk=%s: %s", label, obj.pk, exc)
                self.stdout.write(self.style.SUCCESS(f"{label}: {touched}/{count} row(s) re-encrypted."))
                total_touched += touched

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry run complete. {total_touched} row(s) would be touched."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. {total_touched} row(s) re-encrypted, {total_errors} error(s)."
            ))
