"""
Real-time incident clustering: groups similar tickets from DIFFERENT reporters
on the same team, filed within a short window, into a shared Incident --
signalling a likely outage instead of N unrelated-looking investigations.

This is the cross-reporter sibling of tickets/similarity.py's duplicate
detection (which only looks at the SAME reporter's other open tickets).
Reuses score_similarity so the two features can't drift apart.

Flag-only, never blocking: never raises, never changes ticket status/assignment,
callers still wrap this in try/except (matches the non-fatal style of the
other create-time hooks in tickets/services.py) as defense-in-depth.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .similarity import score_similarity


def _cluster_window_minutes() -> int:
    return int(getattr(settings, "INCIDENT_CLUSTER_WINDOW_MINUTES", 60))


def _cluster_min_size() -> int:
    return int(getattr(settings, "INCIDENT_CLUSTER_MIN_SIZE", 3))


def _cluster_similarity_threshold() -> float:
    return float(getattr(settings, "INCIDENT_CLUSTER_SIMILARITY_THRESHOLD", 0.6))


def find_or_join_incident(ticket):
    """
    Cluster `ticket` with other reporters' similar, still-open tickets on the
    same team filed within the configured window. Joins an existing Incident
    if a matched ticket already belongs to one; otherwise creates a new
    Incident once enough matches accumulate. No-ops (returns None) if the
    ticket has no team -- an Incident must stay scoped to one tenant.
    """
    from .models import Incident, Ticket, TicketInteraction
    from .predictive_routing import OPEN_STATUSES

    if not ticket.team_id:
        return None

    window_start = timezone.now() - timedelta(minutes=_cluster_window_minutes())
    candidates = (
        Ticket.objects
        .filter(
            team_id=ticket.team_id,
            category=ticket.category,
            status__in=OPEN_STATUSES,
            created_at__gte=window_start,
        )
        .exclude(pk=ticket.pk)
        .exclude(user_id=ticket.user_id)
    )

    threshold = _cluster_similarity_threshold()
    matches = [c for c in candidates if score_similarity(ticket, c) >= threshold]

    existing_incident = next((m.incident for m in matches if m.incident_id), None)
    if existing_incident:
        ticket.incident = existing_incident
        ticket.save(update_fields=["incident"])
        TicketInteraction.objects.create(
            ticket=ticket,
            user=ticket.user,
            interaction_type="user_message",
            content=f"[Incident] Linked to incident #{existing_incident.pk} ({existing_incident.tickets.count()} related reports).",
        )
        return existing_incident

    if len(matches) + 1 < _cluster_min_size():
        return None

    incident = Incident.objects.create(
        team_id=ticket.team_id,
        category=ticket.category,
        title=f"Multiple reports: {ticket.issue_type}"[:200],
    )
    member_ids = [ticket.pk] + [m.pk for m in matches]
    Ticket.objects.filter(pk__in=member_ids).update(incident=incident)
    for member_ticket in [ticket] + matches:
        TicketInteraction.objects.create(
            ticket=member_ticket,
            user=member_ticket.user,
            interaction_type="user_message",
            content=f"[Incident] Linked to incident #{incident.pk} ({len(member_ids)} related reports).",
        )
    return incident
