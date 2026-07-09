"""Permissions for compliance audit log access."""

from tickets.scoping import active_team_id_for_user

from monitoring.models import ComplianceAuditEvent


def user_can_view_audit(user) -> bool:
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


def audit_queryset_for_user(user):
    if not user or not user.is_authenticated:
        return ComplianceAuditEvent.objects.none()
    if getattr(user, "is_staff", False):
        return ComplianceAuditEvent.objects.all()
    tid = active_team_id_for_user(user)
    if not tid:
        return ComplianceAuditEvent.objects.none()
    from base.models import Team

    team = Team.objects.filter(pk=tid).first()
    if not team or team.owner_id != user.pk:
        return ComplianceAuditEvent.objects.none()
    return ComplianceAuditEvent.objects.filter(team_id=tid)
