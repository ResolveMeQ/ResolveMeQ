"""
Shared ticket-similarity scoring, used by:
- ai_insights_views.get_similar_tickets (read-only reference material for staff)
- services.create_ticket_with_reporter (duplicate-ticket flagging at creation)

Extracted from ai_insights_views.py so the two callers can't drift apart --
was previously an inline copy in a single view with no other caller.
"""

from __future__ import annotations

from django.conf import settings


def _duplicate_similarity_threshold() -> float:
    return float(getattr(settings, "DUPLICATE_TICKET_SIMILARITY_THRESHOLD", 0.7))


def find_and_flag_duplicate(ticket):
    """
    Flag-only, never blocking: if this ticket looks like the same issue as another
    open ticket the SAME reporter already has, set Ticket.duplicate_of to the best
    match and log a TicketInteraction noting it. Never raises -- callers should
    still wrap this (matches the non-fatal style of the other create-time hooks
    in tickets/services.py), but a caught exception here is defensive-in-depth,
    not the primary safety mechanism.

    Scoped to the same reporter + same category + still-open status: a duplicate
    is "did you already report this", not "does someone else have a similar issue"
    (that's what the separate, cross-user get_similar_tickets reference feature is for).
    """
    from .models import Ticket, TicketInteraction
    from .predictive_routing import OPEN_STATUSES

    candidates = (
        Ticket.objects
        .filter(user_id=ticket.user_id, category=ticket.category, status__in=OPEN_STATUSES)
        .exclude(pk=ticket.pk)
    )
    threshold = _duplicate_similarity_threshold()
    best_match, best_score = None, 0.0
    for candidate in candidates:
        score = score_similarity(ticket, candidate)
        if score > best_score:
            best_match, best_score = candidate, score

    if best_match is None or best_score < threshold:
        return None

    ticket.duplicate_of = best_match
    ticket.save(update_fields=["duplicate_of"])
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="user_message",
        content=f"[Possible duplicate] Looks similar to ticket #{best_match.ticket_id} (score {best_score:.2f}).",
    )
    return best_match


def score_similarity(ticket, other) -> float:
    """
    Weighted similarity 0.0-1.0: category (30%), issue_type keyword overlap (30%),
    description word overlap (20%), same assigned_to (10%), tags overlap (10%).
    """
    score = 0.0

    if other.category == ticket.category:
        score += 0.30

    if ticket.issue_type and other.issue_type:
        ticket_keywords = set(ticket.issue_type.lower().split())
        other_keywords = set(other.issue_type.lower().split())
        if ticket_keywords and other_keywords:
            overlap = len(ticket_keywords & other_keywords) / len(ticket_keywords | other_keywords)
            score += overlap * 0.30

    if ticket.description and other.description:
        ticket_words = set(ticket.description.lower().split())
        other_words = set(other.description.lower().split())
        if ticket_words and other_words:
            overlap = len(ticket_words & other_words) / len(ticket_words | other_words)
            score += overlap * 0.20

    if ticket.assigned_to and other.assigned_to and ticket.assigned_to == other.assigned_to:
        score += 0.10

    if ticket.tags and other.tags:
        ticket_tags = set(ticket.tags)
        other_tags = set(other.tags)
        if ticket_tags and other_tags:
            overlap = len(ticket_tags & other_tags) / len(ticket_tags | other_tags)
            score += overlap * 0.10

    return score
