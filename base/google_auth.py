import re

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


def verify_google_id_token(credential: str) -> dict:
    client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or "").strip()
    if not client_id:
        raise RuntimeError("Google OAuth is not configured")
    return id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        client_id,
    )


def username_from_email(User, email: str) -> str:
    local = (email.split("@")[0] or "user")[:30]
    local = re.sub(r"[^\w.@+-]", "_", local) or "user"
    candidate = local
    n = 0
    while User.objects.filter(username=candidate).exists():
        n += 1
        suffix = f"_{n}"
        candidate = (local[: 150 - len(suffix)] + suffix)[:150]
    return candidate
