"""Shared permission helpers for integration OAuth endpoints."""


def team_from_request(request, *, require_owner: bool = False, owner_detail: str = "Only the workspace owner can manage this integration."):
    from rest_framework.response import Response

    from base.models import Team

    team_id = request.data.get("team_id") or request.GET.get("team_id")
    if not team_id:
        prefs = getattr(request.user, "preferences", None)
        if prefs and prefs.active_team_id:
            team_id = str(prefs.active_team_id)
    if not team_id:
        return None, Response({"detail": "team_id or active_team required."}, status=400)
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return None, Response({"detail": "Team not found."}, status=404)
    if team.owner_id != request.user.pk and not team.members.filter(pk=request.user.pk).exists():
        return None, Response({"detail": "You are not a member of this team."}, status=403)
    if require_owner and team.owner_id != request.user.pk and not getattr(request.user, "is_staff", False):
        return None, Response({"detail": owner_detail}, status=403)
    return team, None
