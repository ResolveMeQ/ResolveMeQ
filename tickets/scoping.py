"""
Ticket visibility for the web portal.

- If the user has a valid **active_team** (member or owner): they see all tickets for that team,
  plus legacy tickets with no team that they created or are assigned to.
- Otherwise: only tickets they created or are assigned to.
- ResolveMeQ platform support staff (`User.is_platform_agent`) additionally see/act on any
  escalated (or previously-claimed) ticket across any team -- the managed-support tier. Scoped
  to escalation only, not blanket account access. See `team_allows_platform_support` below.

Platform staff status itself is Django-admin managed, not self-serve.
"""
from django.db.models import Q

from .models import Ticket


def team_allows_platform_support(team):
    """
    Whether ResolveMeQ staff may pick up escalations for this team.

    Unconditionally True for now (still acquiring customers) -- this is the single hook to
    change when managed support becomes a paid plan/tier: check the team's subscription
    entitlements here instead of returning True, and nothing else in this module needs to change.
    """
    return True


def _platform_agent_has_ticket_access(user, ticket):
    if not getattr(user, "is_platform_agent", False):
        return False
    if not (ticket.status == "escalated" or ticket.claimed_at):
        return False
    return team_allows_platform_support(ticket.team)


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
        own = Q(team_id=tid) | Q(team__isnull=True, user=user) | Q(team__isnull=True, assigned_to=user)
    else:
        own = Q(user=user) | Q(assigned_to=user)

    if getattr(user, "is_platform_agent", False):
        # Escalation-scoped cross-tenant access (see team_allows_platform_support docstring) --
        # OR'd in alongside whatever their own team/ownership already grants them.
        return Ticket.objects.filter(own | Q(status="escalated") | Q(claimed_at__isnull=False))
    return Ticket.objects.filter(own)


def tickets_queryset_for_request(request):
    """Queryset of tickets the current user may list and aggregate."""
    user = getattr(request, "user", None)
    return tickets_queryset_for_user(user)


def user_can_access_ticket(user, ticket):
    """Whether the user may read or act on this ticket (portal)."""
    if not user or not user.is_authenticated:
        return False
    if _platform_agent_has_ticket_access(user, ticket):
        return True
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
    """Assignee must belong to the same team when the ticket is team-scoped -- unless they're
    ResolveMeQ platform support staff picking up an escalation (see team_allows_platform_support)."""
    if getattr(agent_user, "is_platform_agent", False) and team_allows_platform_support(ticket.team):
        return True
    if not ticket.team_id:
        return True
    team = ticket.team
    if team.owner_id == agent_user.id:
        return True
    return team.members.filter(pk=agent_user.pk).exists()
