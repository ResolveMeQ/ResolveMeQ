from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .connector_scoping import team_from_request
from .connectors.jira import normalize_site_url
from .models import JiraInstallation


def _installation_to_dict(inst: JiraInstallation) -> dict:
    return {
        "id": inst.id,
        "site_url": inst.site_url,
        "user_email": inst.user_email,
        "project_key": inst.project_key,
        "issue_type": inst.issue_type,
        "sync_on_escalate": inst.sync_on_escalate,
        "sync_on_resolve": inst.sync_on_resolve,
        "resolve_transition": inst.resolve_transition,
        "is_active": inst.is_active,
        "has_token": bool(inst.api_token),
        "updated_at": inst.updated_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jira_integration_status(request):
    team, err = team_from_request(request)
    if err:
        return err
    inst = (
        JiraInstallation.objects.filter(resolvemeq_team=team, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return Response({
        "connected": bool(inst),
        "installation": _installation_to_dict(inst) if inst else None,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def jira_configure(request):
    team, err = team_from_request(
        request,
        require_owner=True,
        owner_detail="Only the workspace owner can configure Jira.",
    )
    if err:
        return err

    try:
        site_url = normalize_site_url(request.data.get("site_url") or "")
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    user_email = (request.data.get("user_email") or "").strip()
    api_token = (request.data.get("api_token") or "").strip()
    project_key = (request.data.get("project_key") or "SUP").strip().upper()
    if not user_email or not api_token:
        return Response({"error": "user_email and api_token are required."}, status=400)

    JiraInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    inst = JiraInstallation.objects.create(
        resolvemeq_team=team,
        site_url=site_url,
        user_email=user_email[:254],
        api_token=api_token,
        project_key=project_key[:32],
        issue_type=(request.data.get("issue_type") or "Task").strip()[:64],
        sync_on_escalate=bool(request.data.get("sync_on_escalate", True)),
        sync_on_resolve=bool(request.data.get("sync_on_resolve", True)),
        resolve_transition=(request.data.get("resolve_transition") or "Done").strip()[:64],
        installed_by=request.user,
        is_active=True,
    )
    return Response({"installation": _installation_to_dict(inst)}, status=201)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def jira_update(request):
    team, err = team_from_request(
        request,
        require_owner=True,
        owner_detail="Only the workspace owner can update Jira.",
    )
    if err:
        return err
    inst = JiraInstallation.objects.filter(resolvemeq_team=team, is_active=True).first()
    if not inst:
        return Response({"error": "Jira is not connected."}, status=404)

    updates = {}
    if "site_url" in request.data:
        try:
            updates["site_url"] = normalize_site_url(request.data.get("site_url") or "")
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
    if "user_email" in request.data:
        email = (request.data.get("user_email") or "").strip()
        if email:
            updates["user_email"] = email[:254]
    if "api_token" in request.data:
        token = (request.data.get("api_token") or "").strip()
        if token:
            updates["api_token"] = token
    if "project_key" in request.data:
        updates["project_key"] = (request.data.get("project_key") or "").strip().upper()[:32]
    if "issue_type" in request.data:
        updates["issue_type"] = (request.data.get("issue_type") or "").strip()[:64]
    if "sync_on_escalate" in request.data:
        updates["sync_on_escalate"] = bool(request.data.get("sync_on_escalate"))
    if "sync_on_resolve" in request.data:
        updates["sync_on_resolve"] = bool(request.data.get("sync_on_resolve"))
    if "resolve_transition" in request.data:
        updates["resolve_transition"] = (request.data.get("resolve_transition") or "").strip()[:64]

    if updates:
        for field, value in updates.items():
            setattr(inst, field, value)
        inst.save(update_fields=list(updates.keys()) + ["updated_at"])

    return Response({"installation": _installation_to_dict(inst)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def jira_disconnect(request):
    team, err = team_from_request(
        request,
        require_owner=True,
        owner_detail="Only the workspace owner can disconnect Jira.",
    )
    if err:
        return err
    updated = JiraInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    return Response({"disconnected": bool(updated), "team_id": str(team.id)})
