from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from base.msp_scoping import (
    get_msp_hub_for_user,
    max_msp_clients_for_hub,
    msp_client_name,
    msp_client_teams_for_hub,
    user_manages_msp_client,
)
from base.msp_usage import client_usage_metrics, hub_dashboard_payload


def _hub_or_error(request, team_id=None):
    hub = get_msp_hub_for_user(request.user, team_id=team_id)
    if not hub:
        return None, Response({"error": "MSP hub not found or you are not the owner."}, status=404)
    return hub, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def msp_status(request):
    """Whether the current user owns an MSP hub and basic stats."""
    hub = get_msp_hub_for_user(request.user)
    if not hub:
        hubs_owned = Team.objects.filter(owner=request.user, is_active=True).count()
        return Response({
            "enabled": False,
            "can_enable": hubs_owned > 0,
            "hub": None,
        })
    clients = msp_client_teams_for_hub(hub)
    return Response({
        "enabled": True,
        "hub": {"id": str(hub.id), "name": hub.name, "client_count": clients.count()},
        "max_clients": max_msp_clients_for_hub(hub),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def msp_enable(request):
    """
    Enable MSP mode on a workspace the user owns.
    Body: { "team_id": "<uuid>" }
    """
    team_id = request.data.get("team_id")
    if not team_id:
        return Response({"error": "team_id is required."}, status=400)
    try:
        team = Team.objects.get(pk=team_id, owner=request.user, is_active=True)
    except Team.DoesNotExist:
        return Response({"error": "Team not found or you are not the owner."}, status=404)
    if team.team_kind == Team.TEAM_KIND_MSP_CLIENT:
        return Response({"error": "MSP client workspaces cannot become MSP hubs."}, status=400)
    if team.team_kind == Team.TEAM_KIND_MSP:
        return Response({"enabled": True, "hub": {"id": str(team.id), "name": team.name}})
    team.team_kind = Team.TEAM_KIND_MSP
    team.save(update_fields=["team_kind", "updated_at"])
    return Response({"enabled": True, "hub": {"id": str(team.id), "name": team.name}}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def msp_dashboard(request):
    """MSP admin dashboard — all client workspaces with usage metrics."""
    team_id = request.GET.get("team_id")
    hub, err = _hub_or_error(request, team_id=team_id)
    if err:
        return err
    return Response(hub_dashboard_payload(hub, request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def msp_create_client(request):
    """
    Create an isolated client workspace under the MSP hub.
    Body: { "name": "Acme Corp", "description": "...", "team_id": "<msp hub uuid>" }
    """
    team_id = request.data.get("team_id")
    hub, err = _hub_or_error(request, team_id=team_id)
    if err:
        return err

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"error": "name is required."}, status=400)

    current = msp_client_teams_for_hub(hub).count()
    if current >= max_msp_clients_for_hub(hub):
        return Response({"error": "MSP client limit reached for this hub."}, status=403)

    client = Team.objects.create(
        name=msp_client_name(hub, name),
        description=(request.data.get("description") or "").strip(),
        owner=request.user,
        team_kind=Team.TEAM_KIND_MSP_CLIENT,
        msp_parent=hub,
        is_active=True,
    )
    client.members.add(request.user)

    from base.agent_usage import resolve_usage_period

    period_start, period_end = resolve_usage_period(request.user)
    return Response({
        "client": {
            "id": str(client.id),
            "name": client.name,
            "description": client.description,
            "usage": client_usage_metrics(client, period_start=period_start, period_end=period_end),
        },
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def msp_client_usage(request, client_id):
    """Usage metrics for a single MSP client workspace."""
    try:
        client = Team.objects.get(pk=client_id, team_kind=Team.TEAM_KIND_MSP_CLIENT, is_active=True)
    except Team.DoesNotExist:
        return Response({"error": "Client workspace not found."}, status=404)
    if not user_manages_msp_client(request.user, client):
        return Response({"error": "You do not manage this client workspace."}, status=403)

    from base.agent_usage import resolve_usage_period

    period_start, period_end = resolve_usage_period(request.user)
    return Response({
        "client": {"id": str(client.id), "name": client.name},
        "usage": client_usage_metrics(client, period_start=period_start, period_end=period_end),
        "period_start": period_start,
        "period_end": period_end,
    })
