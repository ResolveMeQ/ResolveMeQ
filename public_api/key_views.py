"""Team-owner management of partner API keys (JWT auth)."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from public_api.models import PartnerApiKey, generate_partner_key_pair
from public_api.scopes import DEFAULT_SCOPES, SCOPE_LABELS, normalize_scopes
from tickets.scoping import active_team_id_for_user


def _user_can_manage_keys(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    tid = active_team_id_for_user(user)
    if not tid:
        return False
    team = Team.objects.filter(pk=tid).first()
    return bool(team and team.owner_id == user.pk)


def _key_to_dict(key: PartnerApiKey, *, include_secret: str | None = None) -> dict:
    data = {
        "id": str(key.id),
        "name": key.name,
        "key_prefix": key.key_prefix,
        "scopes": key.scopes or [],
        "is_active": key.is_active,
        "team_id": str(key.team_id),
        "created_at": key.created_at,
        "last_used_at": key.last_used_at,
    }
    if include_secret:
        data["api_key"] = include_secret
    return data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_key_metadata(request):
    return Response({
        "scopes": [{"value": s, "label": SCOPE_LABELS.get(s, s)} for s in DEFAULT_SCOPES],
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def partner_key_list_create(request):
    if not _user_can_manage_keys(request.user):
        return Response({"error": "Only the workspace owner can manage partner API keys."}, status=403)

    tid = active_team_id_for_user(request.user)
    team = Team.objects.filter(pk=tid).first()
    if not team:
        return Response({"error": "Select an active workspace first."}, status=400)

    if request.method == "GET":
        keys = PartnerApiKey.objects.filter(team=team).order_by("-created_at")
        return Response({"keys": [_key_to_dict(k) for k in keys]})

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"error": "name is required."}, status=400)
    try:
        scopes = normalize_scopes(request.data.get("scopes"))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    raw, prefix, hashed = generate_partner_key_pair()
    key = PartnerApiKey.objects.create(
        team=team,
        name=name[:120],
        key_prefix=prefix,
        key_hash=hashed,
        scopes=scopes,
        created_by=request.user,
    )
    return Response({
        "key": _key_to_dict(key, include_secret=raw),
        "message": "Copy the api_key now — it will not be shown again.",
    }, status=201)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def partner_key_revoke(request, key_id):
    if not _user_can_manage_keys(request.user):
        return Response({"error": "Only the workspace owner can manage partner API keys."}, status=403)
    tid = active_team_id_for_user(request.user)
    key = PartnerApiKey.objects.filter(pk=key_id, team_id=tid).first()
    if not key:
        return Response({"error": "API key not found."}, status=404)
    key.is_active = False
    key.save(update_fields=["is_active"])
    return Response({"revoked": True})
