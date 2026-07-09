"""Sync ResolveMeQ tickets to Jira on escalate/resolve."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def maybe_sync_ticket_escalated_to_jira(ticket) -> None:
    if not ticket or not ticket.team_id:
        return
    try:
        from integrations.connectors.jira import create_issue_for_ticket, get_active_installation
        from tickets.models import ExternalReference

        installation = get_active_installation(ticket.team_id)
        if not installation or not installation.sync_on_escalate:
            return
        if ExternalReference.objects.filter(ticket=ticket, system="jira").exists():
            return

        key, url = create_issue_for_ticket(installation, ticket)
        ExternalReference.objects.create(
            ticket=ticket,
            system="jira",
            external_id=key,
            external_url=url,
            metadata={"project_key": installation.project_key, "sync": "escalate"},
        )
        logger.info("Created Jira issue %s for ticket %s", key, ticket.ticket_id)
    except Exception as exc:
        logger.warning("Jira escalate sync failed for ticket %s: %s", ticket.ticket_id, exc)


def maybe_sync_ticket_resolved_to_jira(ticket) -> None:
    if not ticket or not ticket.team_id:
        return
    try:
        from integrations.connectors.jira import get_active_installation, transition_issue
        from tickets.models import ExternalReference

        installation = get_active_installation(ticket.team_id)
        if not installation or not installation.sync_on_resolve:
            return
        ref = ExternalReference.objects.filter(ticket=ticket, system="jira").first()
        if not ref:
            return

        ok = transition_issue(installation, ref.external_id, installation.resolve_transition)
        if ok:
            meta = dict(ref.metadata or {})
            meta["last_sync"] = "resolved"
            ref.metadata = meta
            ref.save(update_fields=["metadata", "updated_at"])
            logger.info("Transitioned Jira issue %s for ticket %s", ref.external_id, ticket.ticket_id)
    except Exception as exc:
        logger.warning("Jira resolve sync failed for ticket %s: %s", ticket.ticket_id, exc)
