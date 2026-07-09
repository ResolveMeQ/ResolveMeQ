import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def _pepper() -> str:
    return (getattr(settings, "PARTNER_API_KEY_PEPPER", None) or settings.SECRET_KEY or "").strip()


def hash_partner_key(raw_key: str) -> str:
    return hashlib.sha256(f"{_pepper()}:{raw_key}".encode()).hexdigest()


def generate_partner_key_pair() -> tuple[str, str, str]:
    """Return (raw_key, key_prefix, key_hash). Raw key shown once to the customer."""
    raw = f"rmq_pk_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    return raw, prefix, hash_partner_key(raw)


def verify_partner_key(raw_key: str, stored_hash: str) -> bool:
    if not raw_key or not stored_hash:
        return False
    return secrets.compare_digest(hash_partner_key(raw_key), stored_hash)


class PartnerApiKey(models.Model):
    """Team-scoped API key for partner integrations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        "base.Team",
        on_delete=models.CASCADE,
        related_name="partner_api_keys",
    )
    name = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=128)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "base.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partner_api_keys_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…)"

    def touch_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])
