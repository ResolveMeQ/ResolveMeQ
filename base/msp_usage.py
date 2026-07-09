"""Per-client usage metrics for MSP dashboards (P3-5)."""

from __future__ import annotations

from typing import Any, Dict, List

from django.utils import timezone


def _connected_integrations(team_id) -> List[str]:
    connected: List[str] = []
    if not team_id:
        return connected
    try:
        from integrations.models import (
            GoogleWorkspaceInstallation,
            JiraInstallation,
            Microsoft365Installation,
            OktaInstallation,
            SlackToken,
        )

        if SlackToken.objects.filter(resolvemeq_team_id=team_id, is_active=True).exists():
            connected.append("slack")
        if OktaInstallation.objects.filter(resolvemeq_team_id=team_id, is_active=True).exists():
            connected.append("okta")
        if GoogleWorkspaceInstallation.objects.filter(resolvemeq_team_id=team_id, is_active=True).exists():
            connected.append("google_workspace")
        if Microsoft365Installation.objects.filter(resolvemeq_team_id=team_id, is_active=True).exists():
            connected.append("microsoft365")
        if JiraInstallation.objects.filter(resolvemeq_team_id=team_id, is_active=True).exists():
            connected.append("jira")
    except Exception:
        pass
    return connected


def client_usage_metrics(team, *, period_start=None, period_end=None) -> Dict[str, Any]:
    from tickets.models import Ticket
    from workflows.models import Workflow, WorkflowTemplate

    now = timezone.now()
    if period_start is None or period_end is None:
        from base.agent_usage import resolve_usage_period

        owner = team.owner
        if owner:
            period_start, period_end = resolve_usage_period(owner, now=now)
        else:
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            from dateutil.relativedelta import relativedelta

            period_end = period_start + relativedelta(months=1)

    ticket_qs = Ticket.objects.filter(team=team)
    wf_qs = Workflow.objects.filter(team=team)
    period_tickets = ticket_qs.filter(created_at__gte=period_start, created_at__lt=period_end)
    period_workflows = wf_qs.filter(created_at__gte=period_start, created_at__lt=period_end)

    return {
        "tickets_created_period": period_tickets.count(),
        "tickets_open": ticket_qs.exclude(status="resolved").count(),
        "workflows_started_period": period_workflows.count(),
        "workflows_completed_period": period_workflows.filter(status="completed").count(),
        "templates_count": WorkflowTemplate.objects.filter(team=team).count(),
        "integrations_connected": _connected_integrations(team.id),
    }


def hub_dashboard_payload(hub, user) -> Dict[str, Any]:
    from base.agent_usage import resolve_usage_period
    from base.msp_scoping import msp_client_teams_for_hub

    period_start, period_end = resolve_usage_period(user)
    clients = []
    for client in msp_client_teams_for_hub(hub):
        clients.append({
            "id": str(client.id),
            "name": client.name,
            "description": client.description,
            "member_count": client.member_count,
            "created_at": client.created_at,
            "usage": client_usage_metrics(client, period_start=period_start, period_end=period_end),
        })
    return {
        "msp_team": {
            "id": str(hub.id),
            "name": hub.name,
            "team_kind": hub.team_kind,
            "client_count": len(clients),
        },
        "clients": clients,
        "period_start": period_start,
        "period_end": period_end,
    }
