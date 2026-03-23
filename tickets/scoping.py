"""
Ticket visibility for the web portal.

- If the user has a valid **active_team** (member or owner): they see all tickets for that team,
  plus legacy tickets with no team that they created or are assigned to.
- Otherwise: only tickets they created or are assigned to.

Platform operations use Django admin, not permission flags here.
"""
from django.db.models import Q

from .models import Ticket


def active_team_id_for_user(user):
    """
    Return UUID string of user's preferences.active_team if they are owner or member, else None.
    """
    if not user or not user.is_authenticated:
        return None
    try:
        prefs = user.preferences
    except Exception:
        return None
    tid = prefs.active_team_id
    if not tid:
        return None
    from base.models import Team

    if not Team.objects.filter(pk=tid).filter(Q(members=user) | Q(owner=user)).exists():
        return None
    return tid


def tickets_queryset_for_user(user):
    """Queryset of tickets visible to this user (no request object)."""
    if not user or not user.is_authenticated:
        return Ticket.objects.none()
    tid = active_team_id_for_user(user)
    if tid:
        return Ticket.objects.filter(
            Q(team_id=tid)
            | Q(team__isnull=True, user=user)
            | Q(team__isnull=True, assigned_to=user)
        )
    return Ticket.objects.filter(Q(user=user) | Q(assigned_to=user))


def tickets_queryset_for_request(request):
    """Queryset of tickets the current user may list and aggregate."""
    user = getattr(request, "user", None)
    return tickets_queryset_for_user(user)


def user_can_access_ticket(user, ticket):
    """Whether the user may read or act on this ticket (portal)."""
    if not user or not user.is_authenticated:
        return False
    tid = active_team_id_for_user(user)
    if tid:
        if ticket.team_id and str(ticket.team_id) == str(tid):
            return True
        if ticket.team_id is None and (
            ticket.user_id == user.id
            or (ticket.assigned_to_id and ticket.assigned_to_id == user.id)
        ):
            return True
        return False
    return ticket.user_id == user.id or (
        ticket.assigned_to_id and ticket.assigned_to_id == user.id
    )


def user_can_assign_agent(ticket, agent_user):
    """Assignee must belong to the same team when the ticket is team-scoped."""
    if not ticket.team_id:
        return True
    team = ticket.team
    if team.owner_id == agent_user.id:
        return True
    return team.members.filter(pk=agent_user.pk).exists()
