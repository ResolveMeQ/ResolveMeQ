"""Permissions for compliance audit log access."""

from base.team_permissions import user_can_view_audit_log
from tickets.scoping import active_team_id_for_user

from monitoring.models import ComplianceAuditEvent


def user_can_view_audit(user) -> bool:
    return user_can_view_audit_log(user)


def audit_queryset_for_user(user):
    if not user or not user.is_authenticated:
        return ComplianceAuditEvent.objects.none()
    if getattr(user, "is_staff", False):
        return ComplianceAuditEvent.objects.all()
    tid = active_team_id_for_user(user)
    if not tid:
        return ComplianceAuditEvent.objects.none()
    if not user_can_view_audit_log(user):
        return ComplianceAuditEvent.objects.none()
    return ComplianceAuditEvent.objects.filter(team_id=tid)
