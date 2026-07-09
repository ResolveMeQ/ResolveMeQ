"""Permissions for webhook endpoint administration."""

from tickets.scoping import active_team_id_for_user

from integrations.models import WebhookEndpoint


def user_can_manage_webhooks(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    tid = active_team_id_for_user(user)
    if not tid:
        return False
    from base.models import Team

    team = Team.objects.filter(pk=tid).first()
    return bool(team and team.owner_id == user.pk)


def webhooks_queryset_for_user(user):
    if not user or not user.is_authenticated:
        return WebhookEndpoint.objects.none()
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
    return endpoint.resolvemeq_team.owner_id == user.pk
