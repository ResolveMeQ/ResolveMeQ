import logging
import urllib.parse

from datetime import timedelta

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .connector_scoping import team_from_request
from .models import GoogleWorkspaceInstallation

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def google_workspace_status(request):
    team, err = team_from_request(request)
    if err:
        return err
    inst = (
        GoogleWorkspaceInstallation.objects.filter(resolvemeq_team=team, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return Response({
        "connected": bool(inst),
        "admin_email": inst.admin_email if inst else None,
        "updated_at": inst.updated_at.isoformat() if inst and inst.updated_at else None,
        "circuit_open": bool(inst and inst.circuit_open_until and inst.circuit_open_until > timezone.now()),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def google_workspace_oauth_start(request):
    team, err = team_from_request(request, require_owner=True, owner_detail="Only the workspace owner can connect Google Workspace.")
    if err:
        return err

    client_id = settings.GOOGLE_WORKSPACE_CLIENT_ID
    redirect_uri = settings.GOOGLE_WORKSPACE_REDIRECT_URI
    if not client_id or not redirect_uri:
        return Response({"detail": "Google Workspace OAuth is not configured."}, status=503)

    signer = TimestampSigner(salt="google-workspace-oauth")
    state = signer.sign(f"{team.id}:{request.user.id}")
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": settings.GOOGLE_WORKSPACE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    authorize_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    if request.GET.get("format") == "json":
        return Response({"authorize_url": authorize_url})
    return HttpResponseRedirect(authorize_url)


@csrf_exempt
def google_workspace_oauth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")
    state = request.GET.get("state", "")
    signer = TimestampSigner(salt="google-workspace-oauth")
    try:
        payload = signer.unsign(state, max_age=900)
    except (BadSignature, SignatureExpired):
        return HttpResponseBadRequest("Invalid or expired state.")

    parts = payload.split(":")
    if len(parts) != 2:
        return HttpResponseBadRequest("Invalid state payload.")
    team_id, user_id = parts

    from base.models import Team

    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return HttpResponseBadRequest("Team not found.")

    client_id = settings.GOOGLE_WORKSPACE_CLIENT_ID
    client_secret = settings.GOOGLE_WORKSPACE_CLIENT_SECRET
    redirect_uri = settings.GOOGLE_WORKSPACE_REDIRECT_URI
    if not client_id or not client_secret or not redirect_uri:
        return HttpResponseBadRequest("Google Workspace OAuth is not configured.")

    from integrations.connectors.base import http_post_json

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    try:
        response = http_post_json(
            "https://oauth2.googleapis.com/token",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
    except Exception:
        logger.exception("Google Workspace token exchange failed for team %s", team_id)
        return HttpResponseBadRequest("Authentication failed, please try again.")
    if response.status_code >= 400:
        return HttpResponseBadRequest(f"Token exchange failed (HTTP {response.status_code}).")

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        return HttpResponseBadRequest("No access token in Google response.")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()

    from integrations.connectors.base import http_get_json

    admin_email = ""
    try:
        profile_resp = http_get_json(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code == 200:
            admin_email = (profile_resp.json().get("email") or "")[:254]
    except Exception:
        logger.exception(
            "Google Workspace profile lookup failed for team %s (user %s)",
            team.id,
            user_id,
        )

    GoogleWorkspaceInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    expires_in = data.get("expires_in")
    expires_at = timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None

    GoogleWorkspaceInstallation.objects.create(
        resolvemeq_team=team,
        admin_email=admin_email,
        access_token=access_token,
        refresh_token=data.get("refresh_token") or "",
        token_expires_at=expires_at,
        scopes=settings.GOOGLE_WORKSPACE_SCOPES,
        installed_by=user,
        is_active=True,
    )

    frontend = settings.FRONTEND_URL.rstrip("/")
    return HttpResponseRedirect(f"{frontend}/settings/integrations?google=connected")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def google_workspace_disconnect(request):
    team, err = team_from_request(request, require_owner=True, owner_detail="Only the workspace owner can disconnect Google Workspace.")
    if err:
        return err
    updated = GoogleWorkspaceInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    return Response({"disconnected": bool(updated), "team_id": str(team.id)})
