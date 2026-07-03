"""
Who may view the escalation queue and claim cross-team escalations (portal).
"""
from __future__ import annotations

from django.db.models import Q

from base.models import Team


def user_can_access_escalation_queue(user) -> bool:
    """
    Platform support staff and team owners (leads) may use the escalation queue.
    Regular team members rely on the Tickets list for their own work.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_platform_agent", False):
        return True
    return Team.objects.filter(owner=user).exists()
