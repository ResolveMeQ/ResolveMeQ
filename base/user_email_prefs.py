"""Read notification preferences for outbound user email."""

from __future__ import annotations

from django.contrib.auth import get_user_model

User = get_user_model()


def _prefs(user):
    from base.models import UserPreferences

    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


def user_accepts_email(user: User) -> bool:
    """Master switch: user allows app notification email (Settings → email notifications)."""
    if not getattr(user, "is_active", True) or not user.email:
        return False
    return _prefs(user).email_notifications


def user_wants_ticket_update_emails(user: User) -> bool:
    if not user_accepts_email(user):
        return False
    return _prefs(user).ticket_updates


def user_wants_digest_emails(user: User) -> bool:
    if not user_accepts_email(user):
        return False
    return _prefs(user).daily_digest


def user_wants_system_alert_emails(user: User) -> bool:
    if not user_accepts_email(user):
        return False
    return _prefs(user).system_alerts
