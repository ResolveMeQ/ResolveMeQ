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

from base.models import Team
from base.team_permissions import user_can_manage_integrations, user_is_team_owner

from .connectors.okta import issuer_for_domain, normalize_okta_domain
from .models import OktaInstallation


def _team_from_request(request, *, require_owner: bool = False):
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
    if require_owner:
        allowed = user_is_team_owner(request.user, team) or user_can_manage_integrations(request.user, team)
        if not allowed and not getattr(request.user, "is_staff", False):
            return None, Response({"detail": "You do not have permission to manage Okta for this workspace."}, status=403)
    return team, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def okta_integration_status(request):
    team, err = _team_from_request(request)
    if err:
        return err
    inst = (
        OktaInstallation.objects.filter(resolvemeq_team=team, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return Response({
        "connected": bool(inst),
        "okta_domain": inst.okta_domain if inst else None,
        "updated_at": inst.updated_at.isoformat() if inst and inst.updated_at else None,
        "circuit_open": bool(inst and inst.circuit_open_until and inst.circuit_open_until > timezone.now()),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def okta_oauth_start(request):
    team, err = _team_from_request(request, require_owner=True)
    if err:
        return err

    raw_domain = request.GET.get("okta_domain") or ""
    try:
        domain = normalize_okta_domain(raw_domain)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    client_id = settings.OKTA_CLIENT_ID
    redirect_uri = settings.OKTA_REDIRECT_URI
    if not client_id or not redirect_uri:
        return Response({"detail": "Okta OAuth is not configured."}, status=503)

    signer = TimestampSigner(salt="okta-oauth-resolvemeq")
    state = signer.sign(f"{team.id}:{request.user.id}:{domain}")
    issuer = issuer_for_domain(domain)
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "scope": settings.OKTA_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
    })
    authorize_url = f"{issuer}/v1/authorize?{params}"
    if request.GET.get("format") == "json":
        return Response({"authorize_url": authorize_url})
    return HttpResponseRedirect(authorize_url)


@csrf_exempt
def okta_oauth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")
    state = request.GET.get("state", "")
    signer = TimestampSigner(salt="okta-oauth-resolvemeq")
    try:
        payload = signer.unsign(state, max_age=900)
    except (BadSignature, SignatureExpired):
        return HttpResponseBadRequest("Invalid or expired state.")

    parts = payload.split(":")
    if len(parts) != 3:
        return HttpResponseBadRequest("Invalid state payload.")
    team_id, user_id, domain = parts
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return HttpResponseBadRequest("Team not found.")

    client_id = settings.OKTA_CLIENT_ID
    client_secret = settings.OKTA_CLIENT_SECRET
    redirect_uri = settings.OKTA_REDIRECT_URI
    if not client_id or not client_secret or not redirect_uri:
        return HttpResponseBadRequest("Okta OAuth is not configured.")

    issuer = issuer_for_domain(domain)
    token_url = f"{issuer}/v1/token"
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")

    from integrations.connectors.base import http_post_json

    try:
        response = http_post_json(
            token_url,
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
        return HttpResponseBadRequest("No access token in Okta response.")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()

    OktaInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    expires_in = data.get("expires_in")
    expires_at = None
    if expires_in:
        expires_at = timezone.now() + timedelta(seconds=int(expires_in))

    OktaInstallation.objects.create(
        resolvemeq_team=team,
        okta_domain=domain,
        issuer_url=issuer,
        access_token=access_token,
        refresh_token=data.get("refresh_token") or "",
        token_expires_at=expires_at,
        scopes=data.get("scope") or settings.OKTA_SCOPES,
        installed_by=user,
        is_active=True,
    )

    frontend = settings.FRONTEND_URL.rstrip("/")
    return HttpResponseRedirect(f"{frontend}/settings/integrations?okta=connected")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def okta_disconnect(request):
    team, err = _team_from_request(request, require_owner=True)
    if err:
        return err
    updated = OktaInstallation.objects.filter(resolvemeq_team=team, is_active=True).update(is_active=False)
    return Response({"disconnected": bool(updated), "team_id": str(team.id)})
