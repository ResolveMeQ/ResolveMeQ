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
from .models import Microsoft365Installation


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def microsoft365_status(request):
    team, err = team_from_request(request)
    if err:
        return err
    inst = (
        Microsoft365Installation.objects.filter(resolvemeq_team=team, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return Response({
        "connected": bool(inst),
        "tenant_id": inst.tenant_id if inst else None,
        "updated_at": inst.updated_at.isoformat() if inst and inst.updated_at else None,
        "circuit_open": bool(inst and inst.circuit_open_until and inst.circuit_open_until > timezone.now()),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def microsoft365_oauth_start(request):
    team, err = team_from_request(request, require_owner=True, owner_detail="Only the workspace owner can connect Microsoft 365.")
    if err:
        return err

    client_id = settings.MICROSOFT365_CLIENT_ID
    redirect_uri = settings.MICROSOFT365_REDIRECT_URI
    if not client_id or not redirect_uri:
        return Response({"detail": "Microsoft 365 OAuth is not configured."}, status=503)

    signer = TimestampSigner(salt="microsoft365-oauth")
    state = signer.sign(f"{team.id}:{request.user.id}")
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": settings.MICROSOFT365_SCOPES,
        "state": state,
    })
    authorize_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{params}"
    if request.GET.get("format") == "json":
        return Response({"authorize_url": authorize_url})
    return HttpResponseRedirect(authorize_url)


@csrf_exempt
def microsoft365_oauth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")
    state = request.GET.get("state", "")
    signer = TimestampSigner(salt="microsoft365-oauth")
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

    client_id = settings.MICROSOFT365_CLIENT_ID
    client_secret = settings.MICROSOFT365_CLIENT_SECRET
    redirect_uri = settings.MICROSOFT365_REDIRECT_URI
    if not client_id or not client_secret or not redirect_uri:
        return HttpResponseBadRequest("Microsoft 365 OAuth is not configured.")

    from integrations.connectors.base import http_post_json

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": settings.MICROSOFT365_SCOPES,
    }).encode("utf-8")
    try:
        response = http_post_json(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
    except Exception as exc:
        return HttpResponseBadRequest(f"Token exchange failed: {exc}")
    if response.status_code >= 400:
        return HttpResponseBadRequest(f"Token exchange failed (HTTP {response.status_code}).")

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        return HttpResponseBadRequest("No access token in Microsoft response.")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()

    tenant_id = ""
    from integrations.connectors.base import http_get_json

    try:
        org_resp = http_get_json(
            "https://graph.microsoft.com/v1.0/organization",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if org_resp.status_code == 200:
            orgs = org_resp.json().get("value") or []
            if orgs:
                tenant_id = (orgs[0].get("id") or "")[:64]
    except Exception:
        pass

    Microsoft365Installation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    expires_in = data.get("expires_in")
    expires_at = timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None

    Microsoft365Installation.objects.create(
        resolvemeq_team=team,
        tenant_id=tenant_id,
        access_token=access_token,
        refresh_token=data.get("refresh_token") or "",
        token_expires_at=expires_at,
        scopes=settings.MICROSOFT365_SCOPES,
        installed_by=user,
        is_active=True,
    )

    frontend = settings.FRONTEND_URL.rstrip("/")
    return HttpResponseRedirect(f"{frontend}/settings/integrations?microsoft=connected")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def microsoft365_disconnect(request):
    team, err = team_from_request(request, require_owner=True, owner_detail="Only the workspace owner can disconnect Microsoft 365.")
    if err:
        return err
    updated = Microsoft365Installation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    return Response({"disconnected": bool(updated), "team_id": str(team.id)})
