"""
Transparent field-level encryption for credentials stored in the DB (OAuth
access/refresh tokens, webhook signing secrets, API keys — see
integrations/models.py). Encryption only activates when both
settings.ENABLE_FIELD_ENCRYPTION is true and FIELD_ENCRYPTION_KEY is set; with
either missing, this behaves exactly like a plain TextField, so shipping this
code can never itself change behavior — only deliberately flipping the flag
(in an environment that also has the key) does.

Reads never hard-fail: from_db_value tries to decrypt, and on ANY failure
(not-yet-encrypted plaintext, wrong/missing key, corrupted value) falls back
to returning the raw stored value unchanged. This means turning encryption on
only affects new writes going forward — existing plaintext rows keep working
exactly as before until they're re-encrypted (naturally, next time that
credential is refreshed, or via manage.py encrypt_existing_credentials).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

_fernet_instance = None
_fernet_key_used = None


def _get_fernet():
    """Cached Fernet instance, rebuilt if FIELD_ENCRYPTION_KEY changes (e.g. in tests
    using override_settings). Returns None if encryption isn't configured/enabled."""
    global _fernet_instance, _fernet_key_used

    if not getattr(settings, "ENABLE_FIELD_ENCRYPTION", False):
        return None
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        return None

    if _fernet_instance is not None and _fernet_key_used == key:
        return _fernet_instance

    from cryptography.fernet import Fernet

    _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    _fernet_key_used = key
    return _fernet_instance


class EncryptedTextField(models.TextField):
    """Drop-in TextField replacement with transparent encrypt-on-write,
    decrypt-on-read (with safe plaintext fallback on read)."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value
        return fernet.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            # Not encrypted yet (pre-migration plaintext), or key mismatch --
            # never crash a read over this; treat as the raw stored value.
            return value
