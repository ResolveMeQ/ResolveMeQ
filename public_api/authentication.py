"""Authentication for partner API keys."""

from __future__ import annotations

from types import SimpleNamespace

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from public_api.models import PartnerApiKey, verify_partner_key


class PartnerPrincipal(SimpleNamespace):
    """Synthetic principal bound to a team + API key (not a User)."""

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


def _extract_raw_key(request) -> str | None:
    auth = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    header = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
    return (header or "").strip() or None


class PartnerAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate partner requests via Bearer token or X-API-Key.
    Keys look like: rmq_pk_<random>
    """

    keyword = "Bearer"

    def authenticate(self, request):
        raw = _extract_raw_key(request)
        if not raw:
            return None
        if not raw.startswith("rmq_pk_"):
            raise AuthenticationFailed("Invalid partner API key format.")
        prefix = raw[:12]
        candidates = PartnerApiKey.objects.filter(key_prefix=prefix, is_active=True).select_related("team")
        for key_obj in candidates:
            if verify_partner_key(raw, key_obj.key_hash):
                key_obj.touch_used()
                principal = PartnerPrincipal(team=key_obj.team, api_key=key_obj, pk=key_obj.pk)
                return (principal, key_obj)
        raise AuthenticationFailed("Invalid or revoked partner API key.")
