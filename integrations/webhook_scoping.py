"""Permissions for webhook endpoint administration."""

from base.team_permissions import user_can_manage_webhooks, user_has_team_permission

from integrations.models import WebhookEndpoint


def webhooks_queryset_for_user(user):
    if not user or not user.is_authenticated:
        return WebhookEndpoint.objects.none()
    from tickets.scoping import active_team_id_for_user

    tid = active_team_id_for_user(user)
    if getattr(user, "is_staff", False):
        return WebhookEndpoint.objects.all()
    if tid:
        return WebhookEndpoint.objects.filter(resolvemeq_team_id=tid)
    return WebhookEndpoint.objects.none()


def user_can_edit_webhook(user, endpoint: WebhookEndpoint) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    team = endpoint.resolvemeq_team
    if not team:
        return False
    return user_has_team_permission(user, team, "manage_webhooks")
