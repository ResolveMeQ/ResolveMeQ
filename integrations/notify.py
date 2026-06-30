"""
Fan-out notification wrapper: one function per ticket-lifecycle *event*, each calling every
connected provider's implementation (Slack, Teams, ...). Call sites in tickets/ import from
here instead of importing each provider's module directly, so adding a new provider later
(the frontend placeholder already says "Discord, and more") means adding one branch here,
not touching every call site again.

Each provider call is independently wrapped so one provider's failure (missing install,
malformed payload, network error) never blocks another's -- this is a *new* failure mode
that didn't exist when there was only one provider, so it's handled explicitly here rather
than relying solely on each provider's own internal exception swallowing.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _safe(provider: str, event: str, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.exception("%s notify failed for %s", provider, event)


def notify_user_agent_response(user_id, ticket_id, agent_response, thread_ts=None):
    from integrations.views import notify_user_agent_response as _slack
    from integrations.teams_views import notify_user_agent_response as _teams

    _safe("slack", "agent_response", _slack, user_id, ticket_id, agent_response, thread_ts=thread_ts)
    _safe("teams", "agent_response", _teams, ticket_id, agent_response)


def notify_user_auto_resolution(user_id, ticket_id, params):
    from integrations.views import notify_user_auto_resolution as _slack
    from integrations.teams_views import notify_user_auto_resolution as _teams

    _safe("slack", "auto_resolution", _slack, user_id, ticket_id, params)
    _safe("teams", "auto_resolution", _teams, ticket_id, params)


def notify_ticket_claimed(user_id, ticket_id, agent_name, eta_text=""):
    from integrations.views import notify_ticket_claimed as _slack
    from integrations.teams_views import notify_ticket_claimed as _teams

    _safe("slack", "ticket_claimed", _slack, user_id, ticket_id, agent_name, eta_text=eta_text)
    _safe("teams", "ticket_claimed", _teams, ticket_id, agent_name, eta_text=eta_text)


def notify_escalation(user_id, ticket_id, params):
    from integrations.views import notify_escalation as _slack
    from integrations.teams_views import notify_escalation as _teams

    _safe("slack", "escalation", _slack, user_id, ticket_id, params)
    _safe("teams", "escalation", _teams, ticket_id, params)


def request_clarification_from_user(user_id, ticket_id, params):
    from integrations.views import request_clarification_from_user as _slack
    from integrations.teams_views import request_clarification_from_user as _teams

    _safe("slack", "request_clarification", _slack, user_id, ticket_id, params)
    _safe("teams", "request_clarification", _teams, ticket_id, params)


def notify_resolution_followup(ticket_id):
    from integrations.views import notify_resolution_followup as _slack
    from integrations.teams_views import notify_resolution_followup as _teams

    _safe("slack", "resolution_followup", _slack, ticket_id)
    _safe("teams", "resolution_followup", _teams, ticket_id)


def notify_user_ticket_resolved(ticket):
    from integrations.views import notify_user_ticket_resolved as _slack
    from integrations.teams_views import notify_user_ticket_resolved as _teams

    _safe("slack", "ticket_resolved", _slack, ticket)
    _safe("teams", "ticket_resolved", _teams, ticket)


def notify_ticket_reporter_message(ticket, *, title: str, body: str, actor_name: str = ""):
    from integrations import slack_installation as slack_inst
    from integrations.teams_views import notify_ticket_reporter_message as _teams

    _safe("slack", "reporter_message", slack_inst.notify_ticket_reporter_message,
          ticket, title=title, body=body, actor_name=actor_name)
    _safe("teams", "reporter_message", _teams, ticket, title=title, body=body, actor_name=actor_name)
